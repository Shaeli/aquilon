#!/usr/bin/env python
# -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# ex: set expandtab softtabstop=4 shiftwidth=4:
#
# Copyright (C) 2010,2011,2012,2013,2014,2015,2016,2018  Contributor
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Give anyone with write access to the database the role they want."""

import argparse
import logging
import os
import re
import sys
from subprocess import Popen, PIPE

logging.basicConfig(level=logging.INFO)
log = logging.getLogger('aqdb.add_role')

SBINDIR = os.path.dirname(os.path.realpath(__file__))
LIBDIR = os.path.join(os.path.dirname(SBINDIR), "lib")

if LIBDIR not in sys.path:
    sys.path.append(LIBDIR)

import aquilon.aqdb.depends  # pylint: disable=W0611
import aquilon.worker.depends  # pylint: disable=W0611
from aquilon.config import Config
from aquilon.aqdb.model import Base, UserPrincipal, Role, Realm
from aquilon.aqdb.db_factory import DbFactory


def parse_cli(*args, **kw):
    parser = argparse.ArgumentParser(
        description='add current user as an admin')

    parser.add_argument('-v', '--verbose',
                        action='store_true',
                        dest='verbose',
                        help='show queries (metadata bind.echo = True)')

    parser.add_argument('-d', '--debug',
                        action='store_true',
                        dest='debug',
                        help='write debug messages on stdout')

    parser.add_argument('-n', '--dry-run',
                        action='store_false',
                        dest='commit',
                        default=True,
                        help='do not add records to the database')

    parser.add_argument('-r', '--role',
                        required=True,
                        help='The role to set for the user')

    return parser.parse_args()


def parse_klist():
    """Run klist and return a (principal, realm) tuple."""

    config = Config()
    klist = config.lookup_tool('klist')
    log.debug("Running %s", klist)
    p = Popen([klist], stdout=PIPE, stderr=2)
    out, err = p.communicate()
    m = re.search(r'^\s*(?:Default p|P)rincipal:\s*(\S.*)@(.*?)$', out, re.M)
    if not m:
        raise ValueError("Could not determine default principal from klist "
                         "output: %s" % out)
    return m.groups()


def main(*args, **kw):
    opts = parse_cli(args, kw)

    if opts.debug:
        log.setLevel(logging.DEBUG)

    (principal, realm) = parse_klist()

    db = DbFactory(verbose=opts.verbose)
    Base.metadata.bind = db.engine

    session = db.Session()

    aqd_role = Role.get_unique(session, opts.role, compel=True)

    dbrealm = Realm.get_unique(session, realm)
    if not dbrealm:
        dbrealm = Realm(name=realm, trusted=False)
        session.add(dbrealm)

    dbuser = UserPrincipal.get_unique(session, name=principal, realm=dbrealm)
    if dbuser:
        if dbuser.role == aqd_role:
            log.info("%s@%s is already an %s, nothing to do",
                     principal, realm, opts.role)
        else:
            log.info("Updating %s %s to %s",
                     dbuser.name, dbuser.role.name, opts.role)
            dbuser.role = aqd_role
    else:
        log.info("Creating %s@%s as %s", principal, realm, opts.role)
        dbuser = UserPrincipal(name=principal, realm=dbrealm, role=aqd_role,
                               comments='User with write access to database')
        session.add(dbuser)

    if opts.commit:
        session.commit()
    elif session.new or session.dirty:
        log.debug("dry-run mode enabled, not running commit()")


if __name__ == '__main__':
    main(sys.argv)
