# coding: utf-8

# nm.debian.org website backend
#
# Copyright (C) 2012  Enrico Zini <enrico@debian.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import tempfile
import os.path
import os
from cStringIO import StringIO

class atomic_writer(object):
    """
    Atomically write to a file
    """
    def __init__(self, fname, mode=0664, sync=True):
        self.fname = fname
        self.mode = mode
        self.sync = sync
        dirname = os.path.dirname(self.fname)
        self.outfd = tempfile.NamedTemporaryFile(dir=dirname)

    def __enter__(self):
        return self.outfd

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.outfd.flush()
            if self.sync:
                os.fdatasync(self.outfd.fileno())
            os.fchmod(self.outfd.fileno(), self.mode)
            os.rename(self.outfd.name, self.fname)
            self.outfd.delete = False
        self.outfd.close()
        return False


def stream_output(proc):
    """
    Take a subprocess.Popen object and generate its output, as pairs of (tag,
    line) couples. Tag can be O for stdout, E for stderr and R for return
    value.

    Note that the output is not line-split.

    R is always the last bit that gets generated.
    """
    import os
    import fcntl
    import select

    fds = [proc.stdout, proc.stderr]
    tags = ["O", "E"]

    # Set both pipes as non-blocking
    for fd in fds:
        fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)

    # Multiplex stdout and stderr with different tags
    while len(fds) > 0:
        s = select.select(fds, (), ())
        for fd in s[0]:
            idx = fds.index(fd)
            buf = fd.read()
            if buf:
                yield tags[idx], buf
            else:
                fds.pop(idx)
                tags.pop(idx)
    res = proc.wait()
    yield "R", res


class StreamStdoutKeepStderr(object):
    """
    Stream lines of standard output from a Popen object, keeping all of its
    stderr inside a StringIO
    """
    def __init__(self, proc):
        self.proc = proc
        self.stderr = StringIO()

    def __iter__(self):
        last_line = None
        for tag, buf in stream_output(self.proc):
            if tag == "O":
                for l in buf.splitlines(True):
                    if last_line is not None:
                        l = last_line + l
                        last_line = None
                    if l.endswith("\n"):
                        yield l
                    else:
                        last_line = l
            elif tag == "E":
                self.stderr.write(buf)
        if last_line is not None:
            yield last_line
