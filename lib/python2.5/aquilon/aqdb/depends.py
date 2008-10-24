#!/ms/dist/python/PROJ/core/2.5.2-1/bin/python
import os
import sys
import fnmatch
import msversion

if not sys.modules.has_key('sqlalchemy'):
    msversion.addpkg('sqlalchemy', '0.4.8', 'dist')
    #msversion.addpkg('sqlalchemy', '0.5beta', 'dev')

if not sys.modules.has_key('cx_Oracle'):
    msversion.addpkg('cx_Oracle','4.4-10.2.0.1','dist')

if not sys.modules.has_key('ipython'):
    msversion.addpkg('ipython','0.8.2','dist')

#if not sys.modules.has_key('migrate.changeset'):
#    msversion.addpkg('sqlalchemy-migrate', '0.4.5', 'dev')

def all_files(root, patterns='*', single_level=False, yield_folders=False):
    """ Expand patterns from semicolon-separated string to list """

    patterns = patterns.split(';')
    for path, subdirs, files in os.walk(root):
        if yield_folders:
            files.extend(subdirs)
        files.sort()
        for name in files:
            for pattern in patterns:
                if fnmatch.fnmatch(name, pattern):
                    yield os.path.join(path, name)
                    break
        if single_level:
            break

def get_files(mydir=None, *args,**kw):
    """ empowers __init__'s to populate __all__ with a filter given below """

    if not mydir:
        mydir = os.getcwd()
    files = []

    for filename in all_files(mydir, '[a-zA-Z]?*.py'):
        files.append(os.path.splitext(os.path.basename(filename))[0])

    return  files

# Copyright (C) 2008 Morgan Stanley
# This module is part of Aquilon

# ex: set expandtab softtabstop=4 shiftwidth=4: -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
