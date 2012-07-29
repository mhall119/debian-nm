from django.db import models
from django.conf import settings
import os.path
import subprocess
from collections import namedtuple
from backend.utils import StreamStdoutKeepStderr

KEYRINGS = getattr(settings, "KEYRINGS", "/srv/keyring.debian.org/keyrings")

WithFingerprint = namedtuple("WithFingerprint", (
    "type", "trust", "bits", "alg", "id", "created", "expiry",
    "misc8", "ownertrust", "uid", "sigclass", "cap", "misc13",
    "flag", "misc15"))

def _check_keyring(keyring, fpr):
    keyring = os.path.join(KEYRINGS, keyring)

    cmd = [
        "gpg",
        "-q", "--no-options", "--no-default-keyring", "--no-auto-check-trustdb", "--trust-model", "always",
        "--keyring", keyring,
        "--with-colons", "--with-fingerprint", "--list-keys", fpr,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    res = dict()
    stdout, stderr = proc.communicate()
    result = proc.wait()
    present = None
    if result == 0:
        present = True
    elif result == 2:
        present = False
    else:
        raise RuntimeError("gpg exited with status %d: %s" % (result, stderr.strip()))
    return present

def _list_keyring(keyring):
    keyring = os.path.join(KEYRINGS, keyring)

    cmd = [
        "gpg",
        "-q", "--no-options", "--no-default-keyring", "--no-auto-check-trustdb", "--trust-model", "always",
        "--keyring", keyring,
        "--with-colons", "--with-fingerprint", "--list-keys",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    fprs = []
    for line in stdout.split("\n"):
        if not line.startswith("fpr"): continue
        fprs.append(line.split(":")[9])
    result = proc.wait()
    if result == 0:
        return fprs
    else:
        raise RuntimeError("gpg exited with status %d: %s" % (result, stderr.strip()))

def _parse_list_keys_line(line):
    res = []
    for i in line.split(":"):
        if not i:
            res.append(None)
        else:
            res.append(i.decode("string_escape"))
    for i in range(len(res), 15):
        res.append(None)
    return WithFingerprint(*res)


def _list_full_keyring(keyring):
    keyring = os.path.join(KEYRINGS, keyring)

    cmd = [
        "gpg",
        "-q", "--no-options", "--no-default-keyring", "--no-auto-check-trustdb", "--trust-model", "always",
        "--keyring", keyring,
        "--with-colons", "--with-fingerprint", "--list-keys",
    ]
    print " ".join(cmd)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.stdin.close()
    lines = StreamStdoutKeepStderr(proc)
    fprs = []
    for line in lines:
        yield _parse_list_keys_line(line)
    result = proc.wait()
    if result != 0:
        raise RuntimeError("gpg exited with status %d: %s" % (result, lines.stderr.getvalue().strip()))


def is_dm(fpr):
    return _check_keyring("debian-maintainers.gpg", fpr)

def is_dd_u(fpr):
    return _check_keyring("debian-keyring.gpg", fpr)

def is_dd_nu(fpr):
    return _check_keyring("debian-nonupload.gpg", fpr)


def list_dm():
    return _list_keyring("debian-maintainers.gpg")

def list_dd_u():
    return _list_keyring("debian-keyring.gpg")

def list_dd_nu():
    return _list_keyring("debian-nonupload.gpg")

def list_emeritus_dd():
    return _list_keyring("emeritus-keyring.gpg")

def list_removed_dd():
    return _list_keyring("removed-keys.pgp")
