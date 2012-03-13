from django.db import models
from django.conf import settings

import datetime
import sys
import os, os.path
import re
import time
import subprocess
import cPickle as pickle
import psycopg2

CACHE_FILE="make-dm-list.cache"

KEYRINGS = getattr(settings, "KEYRINGS", "/srv/keyring.debian.org/keyrings")

# Reused from dak, to exactly follow what they do
#
# <Culus> 'The standard sucks, but my tool is supposed to interoperate
#          with it. I know - I'll fix the suckage and make things
#          incompatible!'
re_parse_maintainer = re.compile(r"^\s*(\S.*\S)\s*\<([^\>]+)\>")
def force_to_utf8(s):
    """
    Forces a string to UTF-8.  If the string isn't already UTF-8,
    it's assumed to be ISO-8859-1.
    """
    try:
        unicode(s, 'utf-8')
        return s
    except UnicodeError:
        latin1_s = unicode(s,'iso8859-1')
        return latin1_s.encode('utf-8')
def fix_maintainer(maintainer):
    """
    Parses a Maintainer or Changed-By field and returns:
      1. an RFC822 compatible version,
      2. an RFC2047 compatible version,
      3. the name
      4. the email

    The name is forced to UTF-8 for both 1. and 3..  If the name field
    contains '.' or ',' (as allowed by Debian policy), 1. and 2. are
    switched to 'email (name)' format.

    """
    maintainer = maintainer.strip()
    if not maintainer:
        return ('', '', '', '')

    if maintainer.find("<") == -1:
        email = maintainer
        name = ""
    elif (maintainer[0] == "<" and maintainer[-1:] == ">"):
        email = maintainer[1:-1]
        name = ""
    else:
        m = re_parse_maintainer.match(maintainer)
        if not m:
            raise ParseMaintError, "Doesn't parse as a valid Maintainer field."
        name = m.group(1)
        email = m.group(2)

    # Force the name to be UTF-8
    name = force_to_utf8(name)

    if email.find("@") == -1 and email.find("buildd_") != 0:
        raise ParseMaintError, "No @ found in email address part."

    return (name, email)

def read_gpg():
    "Read DM info from the DB keyring"
    keyring = os.path.join(KEYRINGS, "debian-maintainers.gpg")
    re_email = re.compile(r"<(.+?)>")
    re_unmangle = re.compile(r"\\x([0-9A-Fa-f][0-9A-Fa-f])")
    proc = subprocess.Popen(["/usr/bin/gpg", "--no-permission-warning", "--with-colons", "--with-fingerprint", "--no-default-keyring", "--keyring", keyring, "--list-keys"], stdout=subprocess.PIPE)
    rec = None
    for line in proc.stdout:
        if line.startswith("pub:"):
            if rec is not None: yield rec
            row = line.strip().split(":")
            # Unmangle gpg output
            uid = re_unmangle.sub(lambda mo: chr(int(mo.group(1), 16)), row[9])
            uid = uid.decode("utf-8", "replace")
            mo = re_email.search(uid)
            if mo:
                email = mo.group(1)
            else:
                email = uid
            rec = dict(sz=int(row[2]), id=row[4], date=row[5], uid=uid, email=email)
        elif line.startswith("fpr:"):
            row = line.strip().split(":")
            rec["fpr"] = row[9]
    if rec is not None: yield rec
    if proc.wait() != 0:
        raise RuntimeError, "gpg exited with error %d" % proc.returncode

def verbose(*args):
    print >>sys.stderr, " ".join(args)
def warning(*args):
    print >>sys.stderr, " ".join(args)

class Maintainers(object):
    def __init__(self):
        self.conn = psycopg2.connect("service=projectb")
        self.conn.set_client_encoding('UTF-8')
        self.db = dict()
        self.dak_names = None
        if os.path.exists(CACHE_FILE) and os.path.getmtime(CACHE_FILE) > time.time() - 3600*12:
            self.load_from_pickle()
            self.timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
        else:
            self.load_from_db()
            self.timestamp = datetime.datetime.now()

    def load_from_pickle(self):
        verbose("Load from cache...")
        self.db = pickle.load(open(CACHE_FILE))

    def save_to_pickle(self):
        pickle.dump(self.db, open(CACHE_FILE, "w"))

    def load_from_db(self):
        verbose("Initialise from the keyring...")
        for rec in read_gpg():
            self.db[rec["fpr"]] = rec

        verbose("Add fingerprint, uid and maintainer IDs...")
        cur = self.conn.cursor()
        cur.execute("""
        SELECT f.fingerprint, f.id, f.uid, m.id
          FROM fingerprint as f, maintainer as m, uid as u
         WHERE f.uid = u.id
           AND m.name LIKE '% <' || u.uid || '>'
        """)
        for row in cur:
            rec = self.db.get(row[0], None)
            if rec is None: continue
            rec["pdb_fid"] = row[1]
            rec["pdb_uid"] = row[2]
            rec["pdb_mid"] = row[3]

        verbose("Validate info and fill in the blanks...")
        self.validate()

        verbose("Load source package information...")
        for rec in self.db.itervalues():
            rec["sources"] = set(self.get_sources(rec))

        self.save_to_pickle()

    def approx_match(self, rec):
        """
        This should not happen. There should be a clear maintainer<->uid
        mapping in dak. But there is not, so here we do what dak does so we can
        tell people what is happening.
        """
        if isinstance(rec, str):
            rec = self.db[rec]

        rec["pdb_m_name"] = None
        rec["pdb_m_email"] = None
        rec["pdb_mid"] = None
        rec["pdb_u_uid"] = None
        rec["pdb_u_name"] = None

        cur = self.conn.cursor()

        # Add fingerprint and uid IDs, which can be matched exactly by fingerprint
        cur.execute("""
        SELECT f.id, f.uid, u.uid, u.name
          FROM fingerprint as f, uid as u
         WHERE f.fingerprint = '%s'
           AND f.uid = u.id
        """ % rec["fpr"])
        for row in cur:
            rec["pdb_fid"] = row[0]
            rec["pdb_uid"] = row[1]
            rec["pdb_u_uid"] = row[2]
            rec["pdb_u_name"] = row[3]

        # Do what dak does to look for maintainer IDs
        if not self.dak_names:
            cur.execute("""
            SELECT id, name
              FROM maintainer
             WHERE name like '%@%'
            """)
            self.dak_names = list(cur)
        for id, name in self.dak_names:
            (name, email) = fix_maintainer(name)
            if email == rec["pdb_u_uid"] or name == rec["pdb_u_name"]:
                rec["pdb_m_name"] = name
                rec["pdb_m_email"] = email
                rec["pdb_mid"] = id

    def validate(self):
        for rec in self.db.itervalues():
            rec["warn_maintmap"] = \
               rec.get("pdb_fid", None) is None or \
               rec.get("pdb_uid", None) is None or \
               rec.get("pdb_mid", None) is None
            self.approx_match(rec)

    def is_dmua(self, source):
        cur = self.conn.cursor()
        cur.execute("""
        SELECT dm_upload_allowed
          FROM source
         WHERE source='%s'
         ORDER BY version DESC
         LIMIT 1
        """ % source)
        res = [row[0] for row in cur]
        return res and all(res)

    def get_sources(self, rec):
        if isinstance(rec, str):
            rec = self.db[rec]
        if rec.get("pdb_mid", None) is None:
            #warning("%s: missing maintainer ID" % rec["uid"])
            return
        cur = self.conn.cursor()
        cur.execute("""
        SELECT s.source
          FROM src_uploaders u, source s
         WHERE u.maintainer = %d and s.id = u.source and s.dm_upload_allowed is True
        """ % rec["pdb_mid"])
        for row in cur:
            if self.is_dmua(row[0]):
                yield row[0]
