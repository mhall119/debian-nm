#!/usr/bin/python

import os
import sys

project_root = '/srv/nm.debian.org/nm2'

os.umask(005)

paths = [project_root]
for path in paths:
    if path not in sys.path:
        sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

import django.core.handlers.wsgi
# application = django.core.handlers.wsgi.WSGIHandler()

# FIXME: hack to remove DACS cookies, which we don't need, but which use ':' in
#        their names, which make python's Cookie.load fail, which means we
#        don't see any cookies at all, which means CSRF middleware fails.
import re
class RemoveDACSCookies(django.core.handlers.wsgi.WSGIHandler):
    re_cleancookies = re.compile(r"DACS:DEBIANORG[^;]+\s*")
    def __call__(self, environ, start_response):
        c = environ.get("HTTP_COOKIE", None)
        if c is not None:
            environ["HTTP_COOKIE"] = self.re_cleancookies.sub("", c, 1)

        return super(RemoveDACSCookies, self).__call__(environ, start_response)
application = RemoveDACSCookies()
