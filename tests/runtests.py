#!/ms/dist/python/PROJ/core/2.5.0/bin/python
# ex: set expandtab softtabstop=4 shiftwidth=4: -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# $Header$
# $Change$
# $DateTime$
# $Author$
# Copyright (C) 2008 Morgan Stanley
#
# This script is part of Aquilon
"""This sets up and runs the broker unit tests."""

import sys
import os
BINDIR = os.path.dirname(os.path.realpath(sys.argv[0]))
SRCDIR = os.path.join(BINDIR, "..")
sys.path.append(os.path.join(SRCDIR, "lib", "python2.5"))

import unittest
from subprocess import Popen
import getopt

from aquilon.config import Config

from broker.orderedsuite import BrokerTestSuite
from aqdb.orderedsuite import DatabaseTestSuite

default_configfile = os.path.join(BINDIR, "unittest.conf")

def usage():
    print >>sys.stderr, """
    %s [--help] [--debug] [--config=configfile]

    --help      returns this message
    --debug     enable debug (not implemented)
    --config    supply an alternate config file

    Note that:
    %s
    will be used by default, and setting the AQDCONF environment variable
    will *not* work to pass in a config.
    """ % (sys.argv[0], default_configfile)

def force_yes(msg):
    print >>sys.stderr, msg
    print >>sys.stderr, """
        Please confirm by typing yes (three letters) and pressing enter.
        """
    answer = sys.stdin.readline()
    if not answer.startswith("yes"):
        print >>sys.stderr, """Aborting."""
        sys.exit(1)

try:
    opts, args = getopt.getopt(sys.argv[1:], "hdc:",
            ["help", "debug", "config="])
except getopt.GetoptError, e:
    print >>sys.stderr, str(e)
    usage()
    sys.exit(2)

configfile = default_configfile
for o, a in opts:
    if o in ("-h", "--help"):
        usage()
        sys.exit()
    elif o in ("-d", "--debug"):
        # ?
        debug = True
    elif o in ("-c", "--config"):
        configfile = a
    else:
        assert False, "unhandled option"

if not os.path.exists(configfile):
    print >>sys.stderr, "configfile %s does not exist" % configfile
    sys.exit(1)

if os.environ.get("AQDCONF") and (os.path.realpath(configfile)
        != os.path.realpath(os.environ["AQDCONF"])):
    force_yes("""Will ignore AQDCONF variable value:
%s
and use
%s
instead.""" % (os.environ["AQDCONF"], configfile))

config = Config(configfile=configfile)
if not config.has_section("unittest"):
    config.add_section("unittest")
if not config.has_option("unittest", "srcdir"):
    config.set("unittest", "srcdir", SRCDIR)

production_database = "LNPO_AQUILON_NY"
if (config.get("database", "vendor") == "oracle" and
        config.get("database", "server") == production_database):
    force_yes("About to run against the production database %s" %
            production_database)

# Maybe just execute this every run...
if not os.path.exists("/var/spool/keytabs/%s" % config.get("broker", "user")):
    p = Popen(("/ms/dist/kerberos/PROJ/krb5_keytab/prod/sbin/krb5_keytab"),
            stdout=1, stderr=2)
    rc = p.wait()

for label in ["quattordir", "kingdir", "swrepdir", ]:
    dir = config.get("broker", label)
    if os.path.exists(dir):
        continue
    try:
        os.makedirs(dir)
    except OSError, e:
        print >>sys.stderr, "Could not create %s: %s" % (dir, e)

dirs = [config.get("database", "dbdir"), config.get("unittest", "scratchdir")]
for label in ["templatesdir", "rundir", "logdir", "profilesdir",
        "depsdir", "hostsdir", "plenarydir", ]:
    dirs.append(config.get("broker", label))

if configfile != default_configfile:
    force_yes(
        "About to remove any of the following directories that exist:\n%s\n"
        % "\n".join(dirs))

for dir in dirs:
    if os.path.exists(dir):
        print "Removing %s" % dir
        p = Popen(("/bin/rm", "-rf", dir), stdout=1, stderr=2)
        rc = p.wait()
        # FIXME: check rc
    try:
        os.makedirs(dir)
    except OSError, e:
        print >>sys.stderr, "Could not create %s: %s" % (dir, e)

# The template-king also gets synced as part of the broker tests,
# but this makes it available for the initial database build.
p = Popen(("rsync", "-avP", "-e", "ssh", "--delete",
    "quattorsrv:/var/quattor/template-king",
    # Minor hack... ignores config kingdir...
    config.get("broker", "quattordir")),
    stdout=1, stderr=2)
rc = p.wait()
# FIXME: check rc

# The swrep/repository is currently *only* synced here at the top level.
p = Popen(("rsync", "-avP", "-e", "ssh", "--delete",
    "quattorsrv:/var/quattor/swrep/repository",
    config.get("broker", "swrepdir")),
    stdout=1, stderr=2)
rc = p.wait()
# FIXME: check rc

# XXX: Database rebuild is currently broken for oracle if trying to build a
# user in a database where some other user has already created the table.
# Commenting this out for now, and adding a hack below.
#if config.get('database', 'vendor') == 'oracle':
#    # Nuke the database first... (for sqlite, the rebuild script moves
#    # it out of the way)
#    # This method will prompt on stdin for confirmation.
#    from aquilon.aqdb.db import drop_all_tables_and_sequences
#    drop_all_tables_and_sequences()

suite = unittest.TestSuite()
# XXX: Hack - remove the conditional when oracle rebuild works consistently.
if config.get('database', 'vendor') == 'sqlite':
    suite.addTest(DatabaseTestSuite())
suite.addTest(BrokerTestSuite())
unittest.TextTestRunner(verbosity=2).run(suite)
