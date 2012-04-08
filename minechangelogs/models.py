from django.db import models
from django.conf import settings
import logging
import projectb.models as pmodels
from backend import utils
import time
import re
import os
import os.path
import email.utils
import cPickle as pickle
import xapian

log = logging.getLogger(__name__)

MINECHANGELOGS_CACHEDIR = getattr(settings, "MINECHANGELOGS_CACHEDIR", "./data/mc_cache")
MINECHANGELOGS_INDEXDIR = getattr(settings, "MINECHANGELOGS_INDEXDIR", "./data/mc_index")

def parse_changelog(fname):
    """
    Generate changelog entries reading from a file
    """
    log.info("%s: reading changelog entries", fname)
    re_pkg = re.compile(r"^(\S+) \(([^)]+)\)")
    re_ts_line = re.compile(r"^ --(.+>)\s+(\w+\s*,\s*\d+\s+\w+\s*\d+\s+\d+:\d+:\d+)")
    count = 0
    with open(fname) as infd:
        in_changelog = False
        tag = ""
        lines = []
        for line in infd:
            mo = re_pkg.match(line)
            if mo:
                in_changelog = True
                lines = []
                tag = "%s_%s" % (mo.group(1), mo.group(2))
            else:
                mo = re_ts_line.match(line)
                if mo:
                    in_changelog = False
                    count += 1
                    yield tag, mo.group(2), mo.group(1), "".join(lines)

            if in_changelog:
                lines.append(line)
    log.info("%s: %d changelog entries found", fname, count)


class parse_projectb(object):
    """
    Extract changelog entries from projectb, checkpointing all the last
    extracted entries to a pickled cache file.

    This works as a context manager:

        with parse_projectb() as changes:
            for changelog_entry in changes:
                process(changelog_entry)
    """
    def __init__(self, statefile=None):
        if statefile is None:
            statefile = os.path.join(MINECHANGELOGS_CACHEDIR, "index-checkpoint.pickle")
        self.statefile = statefile

    def load_state(self):
        """
        Read the last saved state
        """
        try:
            with open(self.statefile) as infd:
                self.state = pickle.load(infd)
        except IOError:
            self.state = dict()

    def save_state(self):
        """
        Atomically commit the state to disk
        """
        # Ensure the cache dir exists
        dirname = os.path.dirname(self.statefile)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)

        with utils.atomic_writer(self.statefile) as outfd:
            pickle.dump(self.state, outfd, pickle.HIGHEST_PROTOCOL)

    def get_changes(self):
        """
        Produce information about new uploads since the last run
        """
        cur = pmodels.cursor()

        # Read last checkpoint state
        old_seen = self.state.get("old_seen", None)
        old_seen_ids = self.state.get("old_seen_ids", [])

        # Get the new changes, limited to the newest version
        q = """
SELECT c.id, c.seen, c.source, c.version,
       c.date, c.changedby, ch.changelog
  FROM changes c
  JOIN changelogs ch ON ch.id=c.changelog_id
"""
        if old_seen is None:
            cur.execute(q + " ORDER BY seen")
            #cur.execute(q + " WHERE seen >= '2011-07-01 00:00:00' ORDER BY seen")
        else:
            cur.execute(q + " WHERE seen >= %s ORDER BY seen", (old_seen,))

        log.info("projectb: querying changelogs...")
        last_year = None
        last_year_count = 0
        for id, seen, source, version, date, changedby, changelog in cur:
            if last_year is None or last_year != seen.year:
                if last_year is None:
                    log.info("projectb: start of changelog stream.")
                else:
                    log.info("projectb:%d: %d entries read.", last_year, last_year_count)
                last_year = seen.year
                last_year_count = 0
            # Skip the rare cases of partially processed multiple sources on the same instant
            if id in old_seen_ids: continue
            if old_seen is None or seen > old_seen:
                old_seen = seen
                old_seen_ids = []
            old_seen_ids.append(id)

            # Pass on the info to be indexed
            yield "%s_%s" % (source, version), date, changedby, changelog
            last_year_count += 1
        log.info("projectb:%s: %d entries read. End of changelogs stream.", last_year, last_year_count)

        self.state["old_seen"] = old_seen
        self.state["old_seen_ids"] = old_seen_ids

    def __enter__(self):
        self.load_state()
        return self.get_changes()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.save_state()
        return False


class Indexer(object):
    def __init__(self):
        if not os.path.isdir(MINECHANGELOGS_INDEXDIR):
            os.makedirs(MINECHANGELOGS_INDEXDIR)
        self.xdb = xapian.WritableDatabase(MINECHANGELOGS_INDEXDIR, xapian.DB_CREATE_OR_OPEN)
        self.xdb.begin_transaction()
        self.re_split = re.compile(r"[^\w_@.-]+")
        self.re_ts = re.compile(r"(\w+\s*,\s*\d+\s+\w+\s*\d+\s+\d+:\d+:\d+)")
        self.max_ts = None

    def tokenise(self, s):
        return self.re_split.split(s)

    def index(self, entries):
        count = 0
        for tag, date, changedby, changelog in entries:
            count += 1
            #if count % 1000 == 0:
            #    print date
            xid = "XP" + tag
            document = xapian.Document()
            document.set_data(changelog + "\n" + " -- " + changedby + "  " + date)
            #print date
            # Ignore timezones for our purposes: dealing with timezones in
            # python means dealing with one of the most demented pieces of code
            # people have ever conceived, or otherwise it means introducing
            # piles of external dependencies that maybe do the job. We can get
            # away without timezones, it is a lucky thing and we take advantage
            # of such strokes of luck.
            ts = 0
            mo = self.re_ts.match(date)
            if mo:
                #ts = time.mktime(time.strptime(mo.group(1), "%a, %d %b %Y %H:%M:%S"))
                parsed = email.utils.parsedate_tz(mo.group(1))
                if parsed is not None:
                    ts = time.mktime(parsed[:9])
            #parsed = dateutil.parser.parse(date)
            #parsed = email.utils.parsedate_tz(date)
            #ts = time.mktime(parsed[:9]) - parsed[9]
            document.add_value(0, xapian.sortable_serialise(ts))
            document.add_term(xid)
            pos = 0
            lines = changelog.split("\n")[1:]
            lines.append(changedby)
            for l in lines:
                for tok in self.tokenise(l):
                    tok = tok.strip(".-")
                    if not tok: continue
                    # see ircd (2.10.04+-1)
                    if len(tok) > 100: continue
                    if tok.isdigit(): continue
                    document.add_posting(tok, pos)
                    pos += 1
            self.xdb.replace_document(xid, document)
            if self.max_ts is None or ts > self.max_ts:
                self.max_ts = ts

    def flush(self):
        """
        Flush and save indexing information
        """
        if self.max_ts is None:
            self.xdb.set_metadata("max_ts", "0")
        else:
            self.xdb.set_metadata("max_ts", str(self.max_ts))
        self.xdb.set_metadata("last_indexed", str(time.time()))
        self.xdb.commit_transaction()

def info():
    """
    Get information about the state of the minechangelogs database
    """
    xdb = xapian.Database(MINECHANGELOGS_INDEXDIR)
    return dict(
        max_ts = float(xdb.get_metadata("max_ts")),
        last_indexed = float(xdb.get_metadata("last_indexed")),
    )

def query(keywords):
    """
    Get changelog entries matching the given keywords
    """
    xdb = xapian.Database(MINECHANGELOGS_INDEXDIR)

    q = None
    for a in keywords:
        a = a.strip()
        if not a: continue
        if ' ' in a:
            a = a.split()
            p = xapian.Query(xapian.Query.OP_PHRASE, a)
        else:
            p = xapian.Query(a)
        if q is None:
            q = p
        else:
            q = xapian.Query(xapian.Query.OP_OR, q, p)
    if q is None: return

    enquire = xapian.Enquire(xdb)
    enquire.set_query(q)
    enquire.set_sort_by_value(0, True)

    first = 0
    while True:
        matches = enquire.get_mset(first, 100)
        count = matches.size()
        if count == 0: break
        for m in matches:
            yield m.document.get_data()
        first += 100
