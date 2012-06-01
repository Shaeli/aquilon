# -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# ex: set expandtab softtabstop=4 shiftwidth=4:
#
# Copyright (C) 2008,2009,2010,2011,2012,2013  Contributor
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
"""Basic module for running tests on broker commands."""

import os
import sys
import unittest2 as unittest
from subprocess import Popen, PIPE
import re

from aquilon.config import Config
from aquilon.worker import depends  # pylint: disable=W0611

from networktest import DummyNetworks

LOCK_RE = re.compile(r'^(acquired|releasing) exclusive\(.*\), shared\(.*\)\n',
                     re.M)

DSDB_EXPECT_SUCCESS_FILE = "expected_dsdb_cmds"
DSDB_EXPECT_FAILURE_FILE = "fail_expected_dsdb_cmds"
DSDB_EXPECT_FAILURE_ERROR = "fail_expected_dsdb_error"
DSDB_ISSUED_CMDS_FILE = "issued_dsdb_cmds"


class TestBrokerCommand(unittest.TestCase):

    config = None
    scratchdir = None
    dsdb_coverage_dir = None
    sandboxdir = None
    user = None

    aurora_with_node = "oy604c2n6"
    aurora_without_node = "pissp1"
    aurora_without_rack = "oy605c2n6"

    @classmethod
    def setUpClass(cls):
        cls.config = Config()
        cls.net = DummyNetworks(cls.config)

        cls.scratchdir = cls.config.get("unittest", "scratchdir")
        cls.dsdb_coverage_dir = os.path.join(cls.scratchdir, "dsdb_coverage")

        dirs = [cls.scratchdir, cls.dsdb_coverage_dir]
        for dir in dirs:
            if not os.path.exists(dir):
                os.makedirs(dir)

        cls.user = cls.config.get("broker", "user")
        cls.sandboxdir = os.path.join(cls.config.get("broker", "templatesdir"),
                                      cls.user)

        cls.template_extension = cls.config.get("panc", "template_extension")
        cls.gzip_profiles = cls.config.getboolean("panc", "gzip_output")
        cls.profile_suffix = ".xml.gz" if cls.gzip_profiles else ".xml"

        # Need to import protocol buffers after we have the config
        # object all squared away and we can set the sys.path
        # variable appropriately.
        # It would be simpler just to change sys.path in runtests.py,
        # but this allows for each test to be run individually (without
        # the runtests.py wrapper).
        protodir = cls.config.get("protocols", "directory")
        if protodir not in sys.path:
            sys.path.append(protodir)
        for m in ['aqdsystems_pb2', 'aqdnetworks_pb2', 'aqdservices_pb2',
                  'aqddnsdomains_pb2', 'aqdlocations_pb2', 'aqdaudit_pb2',
                  'aqdparamdefinitions_pb2', 'aqdparameters_pb2']:
            globals()[m] = __import__(m)

    def setUp(self):
        for name in [DSDB_EXPECT_SUCCESS_FILE, DSDB_EXPECT_FAILURE_FILE,
                     DSDB_ISSUED_CMDS_FILE, DSDB_EXPECT_FAILURE_ERROR]:
            path = os.path.join(self.dsdb_coverage_dir, name)
            try:
                os.remove(path)
            except OSError:
                pass

    def tearDown(self):
        pass

    def template_name(self, *template, **args):
        if args.get("sandbox", None):
            dir = os.path.join(self.sandboxdir, args.get("sandbox"))
        elif args.get("domain", None):
            dir = os.path.join(self.config.get("broker", "domainsdir"),
                               args.get("domain"))
        else:
            self.assert_(0, "template_name() called without domain or sandbox")
        return os.path.join(dir, *template) + self.template_extension

    def plenary_name(self, *template):
        dir = self.config.get("broker", "plenarydir")
        return os.path.join(dir, *template) + self.template_extension

    def find_template(self, *template, **args):
        """ Figure out the extension of an existing template """
        if args.get("sandbox", None):
            dir = os.path.join(self.sandboxdir, args.get("sandbox"))
        elif args.get("domain", None):
            dir = os.path.join(self.config.get("broker", "domainsdir"),
                               args.get("domain"))
        else:
            self.assert_(0, "find_template() called without domain or sandbox")

        base = os.path.join(dir, *template)

        for extension in [".tpl", ".pan"]:
            if os.path.exists(base + extension):
                return base + extension
        self.assert_(0, "template %s does not exist with any extension" % base)

    def build_profile_name(self, *template, **args):
        base = os.path.join(self.config.get("broker", "builddir"),
                            "domains", args.get("domain"),
                            "profiles", *template)
        return base + self.template_extension

    msversion_dev_re = re.compile('WARNING:msversion:Loading \S* from dev\n')

    def runcommand(self, command, auth=True, **kwargs):
        aq = os.path.join(self.config.get("broker", "srcdir"), "bin", "aq.py")
        if auth:
            port = self.config.get("broker", "kncport")
        else:
            port = self.config.get("broker", "openport")
        if isinstance(command, list):
            args = [str(cmd) for cmd in command]
        else:
            args = [command]
        args.insert(0, sys.executable)
        args.insert(1, aq)
        if "--aqport" not in args:
            args.append("--aqport")
            args.append(port)
        if auth:
            args.append("--aqservice")
            args.append(self.config.get("broker", "service"))
        else:
            args.append("--noauth")
        if "env" in kwargs:
            # Make sure that kerberos tickets are still present if the
            # environment is being overridden...
            env = {}
            for (key, value) in kwargs["env"].items():
                env[key] = value
            for (key, value) in os.environ.items():
                if key.find("KRB") == 0 and key not in env:
                    env[key] = value
            if 'USER' not in env:
                env['USER'] = os.environ.get('USER', '')
            kwargs["env"] = env
        p = Popen(args, stdout=PIPE, stderr=PIPE, **kwargs)
        (out, err) = p.communicate()
        # Strip any msversion dev warnings out of STDERR
        err = self.msversion_dev_re.sub('', err)
        # Lock messages are pretty common...
        err = err.replace('Client status messages disabled, '
                          'retries exceeded.\n', '')
        err = LOCK_RE.sub('', err)
        return (p, out, err)

    def successtest(self, command, **kwargs):
        (p, out, err) = self.runcommand(command, **kwargs)
        self.assertEqual(p.returncode, 0,
                         "Non-zero return code for %s, "
                         "STDOUT:\n@@@\n'%s'\n@@@\n"
                         "STDERR:\n@@@\n'%s'\n@@@\n"
                         % (command, out, err))
        return (out, err)

    def statustest(self, command, **kwargs):
        (out, err) = self.successtest(command, **kwargs)
        self.assertEmptyOut(out, command)
        return err

    def failuretest(self, command, returncode, **kwargs):
        (p, out, err) = self.runcommand(command, **kwargs)
        self.assertEqual(p.returncode, returncode,
                         "Non-%s return code %s for %s, "
                         "STDOUT:\n@@@\n'%s'\n@@@\n"
                         "STDERR:\n@@@\n'%s'\n@@@\n"
                         % (returncode, p.returncode, command, out, err))
        return (out, err)

    def assertEmptyStream(self, name, contents, command):
        self.assertEqual(contents, "",
                         "%s for %s was not empty:\n@@@\n'%s'\n@@@\n"
                         % (name, command, contents))

    def assertEmptyErr(self, contents, command):
        self.assertEmptyStream("STDERR", contents, command)

    def assertEmptyOut(self, contents, command):
        self.assertEmptyStream("STDOUT", contents, command)

    def commandtest(self, command, **kwargs):
        (p, out, err) = self.runcommand(command, **kwargs)
        self.assertEmptyErr(err, command)
        self.assertEqual(p.returncode, 0,
                         "Non-zero return code for %s, "
                         "STDOUT:\n@@@\n'%s'\n@@@\n"
                         % (command, out))
        return out

    def noouttest(self, command, **kwargs):
        out = self.commandtest(command, **kwargs)
        self.assertEqual(out, "",
                         "STDOUT for %s was not empty:\n@@@\n'%s'\n@@@\n"
                         % (command, out))

    def ignoreoutputtest(self, command, **kwargs):
        (p, out, err) = self.runcommand(command, **kwargs)
        # Ignore out/err unless we get a non-zero return code, then log it.
        self.assertEqual(p.returncode, 0,
                         "Non-zero return code for %s, "
                         "STDOUT:\n@@@\n'%s'\n@@@\n"
                         "STDERR:\n@@@\n'%s'\n@@@\n"
                         % (command, out, err))
        return

    # Right now, commands are not implemented consistently.  When that is
    # addressed, this unit test should be updated.
    def notfoundtest(self, command, **kwargs):
        (p, out, err) = self.runcommand(command, **kwargs)
        if p.returncode == 0:
            self.assertEqual(err, "",
                             "STDERR for %s was not empty:\n@@@\n'%s'\n@@@\n" %
                             (command, err))
            self.assertEqual(out, "",
                             "STDOUT for %s was not empty:\n@@@\n'%s'\n@@@\n" %
                             (command, out))
        else:
            self.assertEqual(p.returncode, 4,
                             "Return code for %s was %d instead of %d"
                             "\nSTDOUT:\n@@@\n'%s'\n@@@"
                             "\nSTDERR:\n@@@\n'%s'\n@@@" %
                             (command, p.returncode, 4, out, err))
            self.assertEqual(out, "",
                             "STDOUT for %s was not empty:\n@@@\n'%s'\n@@@\n" %
                             (command, out))
            self.failUnless(err.find("Not Found") >= 0,
                            "STDERR for %s did not include Not Found:"
                            "\n@@@\n'%s'\n@@@\n" %
                            (command, err))
        return err

    def badrequesttest(self, command, ignoreout=False, **kwargs):
        (p, out, err) = self.runcommand(command, **kwargs)
        self.assertEqual(p.returncode, 4,
                         "Return code for %s was %d instead of %d"
                         "\nSTDOUT:\n@@@\n'%s'\n@@@"
                         "\nSTDERR:\n@@@\n'%s'\n@@@" %
                         (command, p.returncode, 4, out, err))
        self.failUnless(err.find("Bad Request") >= 0,
                        "STDERR for %s did not include Bad Request:"
                        "\n@@@\n'%s'\n@@@\n" %
                        (command, err))
        if not ignoreout and "--debug" not in command:
            self.assertEqual(out, "",
                             "STDOUT for %s was not empty:\n@@@\n'%s'\n@@@\n" %
                             (command, out))
        return err

    def unauthorizedtest(self, command, auth=False, msgcheck=True, **kwargs):
        (p, out, err) = self.runcommand(command, auth=auth, **kwargs)
        self.assertEqual(p.returncode, 4,
                         "Return code for %s was %d instead of %d"
                         "\nSTDOUT:\n@@@\n'%s'\n@@@"
                         "\nSTDERR:\n@@@\n'%s'\n@@@" %
                         (command, p.returncode, 4, out, err))
        self.assertEqual(out, "",
                         "STDOUT for %s was not empty:\n@@@\n'%s'\n@@@\n" %
                         (command, out))
        self.failUnless(err.find("Unauthorized:") >= 0,
                        "STDERR for %s did not include Unauthorized:"
                        "\n@@@\n'%s'\n@@@\n" %
                        (command, err))
        if msgcheck:
            self.searchoutput(err, r"Unauthorized (anonymous )?access attempt",
                              command)
        return err

    def internalerrortest(self, command, **kwargs):
        (p, out, err) = self.runcommand(command, **kwargs)
        self.assertEqual(p.returncode, 5,
                         "Return code for %s was %d instead of %d"
                         "\nSTDOUT:\n@@@\n'%s'\n@@@"
                         "\nSTDERR:\n@@@\n'%s'\n@@@" %
                         (command, p.returncode, 5, out, err))
        self.assertEqual(out, "",
                         "STDOUT for %s was not empty:\n@@@\n'%s'\n@@@\n" %
                         (command, out))
        self.assertEqual(err.find("Internal Server Error"), 0,
                         "STDERR for %s did not start with "
                         "Internal Server Error:\n@@@\n'%s'\n@@@\n" %
                         (command, err))
        return err

    def unimplementederrortest(self, command, **kwargs):
        (p, out, err) = self.runcommand(command, **kwargs)
        self.assertEqual(p.returncode, 5,
                         "Return code for %s was %d instead of %d"
                         "\nSTDOUT:\n@@@\n'%s'\n@@@"
                         "\nSTDERR:\n@@@\n'%s'\n@@@" %
                         (command, p.returncode, 5, out, err))
        self.assertEqual(out, "",
                         "STDOUT for %s was not empty:\n@@@\n'%s'\n@@@\n" %
                         (command, out))
        self.assertEqual(err.find("Not Implemented"), 0,
                         "STDERR for %s did not start with "
                         "Not Implemented:\n@@@\n'%s'\n@@@\n" %
                         (command, err))
        return err

    # Test for conflicting or invalid aq client options.
    def badoptiontest(self, command, **kwargs):
        (p, out, err) = self.runcommand(command, **kwargs)
        self.assertEqual(p.returncode, 2,
                         "Return code for %s was %d instead of %d"
                         "\nSTDOUT:\n@@@\n'%s'\n@@@"
                         "\nSTDERR:\n@@@\n'%s'\n@@@" %
                         (command, p.returncode, 2, out, err))
        self.assertEqual(out, "",
                         "STDOUT for %s was not empty:\n@@@\n'%s'\n@@@\n" %
                         (command, out))
        return err

    def partialerrortest(self, command, **kwargs):
        # Currently these two cases behave the same way - same exit code
        # and behavior.
        return self.badoptiontest(command, **kwargs)

    def matchoutput(self, out, s, command):
        self.assert_(out.find(s) >= 0,
                     "output for %s did not include '%s':\n@@@\n'%s'\n@@@\n" %
                     (command, s, out))

    def matchclean(self, out, s, command):
        self.assert_(out.find(s) < 0,
                     "output for %s includes '%s':\n@@@\n'%s'\n@@@\n" %
                     (command, s, out))

    def searchoutput(self, out, r, command):
        if isinstance(r, str):
            m = re.search(r, out, re.MULTILINE)
        else:
            m = re.search(r, out)
        self.failUnless(m,
                        "output for %s did not match '%s':\n@@@\n'%s'\n@@@\n"
                        % (command, r, out))
        return m

    def searchclean(self, out, r, command):
        if isinstance(r, str):
            m = re.search(r, out, re.MULTILINE)
        else:
            m = re.search(r, out)
        self.failIf(m,
                    "output for %s matches '%s':\n@@@\n'%s'\n@@@\n" %
                    (command, r, out))

    def parse_proto_msg(self, listclass, attr, msg, expect=None):
        protolist = listclass()
        protolist.ParseFromString(msg)
        received = len(getattr(protolist, attr))
        if expect is None:
            self.failUnless(received > 0,
                            "No %s listed in %s protobuf message\n" %
                            (attr, listclass))
        else:
            self.failUnlessEqual(received, expect,
                                 "%d %s expected, got %d\n" %
                                 (expect, attr, received))
        return protolist

    def parse_netlist_msg(self, msg, expect=None):
        return self.parse_proto_msg(aqdnetworks_pb2.NetworkList,
                                    'networks',
                                    msg, expect)

    def parse_hostlist_msg(self, msg, expect=None):
        return self.parse_proto_msg(aqdsystems_pb2.HostList,
                                    'hosts',
                                    msg, expect)

    def parse_clusters_msg(self, msg, expect=None):
        return self.parse_proto_msg(aqdsystems_pb2.ClusterList,
                                    'clusters',
                                    msg, expect)

    def parse_location_msg(self, msg, expect=None):
        return self.parse_proto_msg(aqdlocations_pb2.LocationList,
                                    'locations',
                                    msg, expect)

    def parse_dns_domainlist_msg(self, msg, expect=None):
        return self.parse_proto_msg(aqddnsdomains_pb2.DNSDomainList,
                                    'dns_domains',
                                    msg, expect)

    def parse_service_msg(self, msg, expect=None):
        return self.parse_proto_msg(aqdservices_pb2.ServiceList,
                                    'services',
                                    msg, expect)

    def parse_servicemap_msg(self, msg, expect=None):
        return self.parse_proto_msg(aqdservices_pb2.ServiceMapList,
                                    'servicemaps',
                                    msg, expect)

    def parse_personality_msg(self, msg, expect=None):
        return self.parse_proto_msg(aqdsystems_pb2.PersonalityList,
                                    'personalities',
                                    msg, expect)

    def parse_os_msg(self, msg, expect=None):
        return self.parse_proto_msg(aqdsystems_pb2.OperatingSystemList,
                                    'operating_systems',
                                    msg, expect)

    def parse_audit_msg(self, msg, expect=None):
        return self.parse_proto_msg(aqdaudit_pb2.TransactionList,
                                    'transactions', msg, expect)

    def parse_resourcelist_msg(self, msg, expect=None):
        return self.parse_proto_msg(aqdsystems_pb2.ResourceList,
                                    'resources',
                                    msg, expect)

    def parse_paramdefinition_msg(self, msg, expect=None):
        return self.parse_proto_msg(aqdparamdefinitions_pb2.ParamDefinitionList,
                                    'param_definitions', msg, expect)

    def parse_parameters_msg(self, msg, expect=None):
        return self.parse_proto_msg(aqdparameters_pb2.ParameterList,
                                    'parameters', msg, expect)

    @classmethod
    def gitenv(cls, env=None):
        """Configure a known sanitised environment"""
        git_path = cls.config.get("broker", "git_path")
        # The "publish" test abuses gitenv(), and it needs the Python interpreter
        # in the path, because it runs the template unit tests which in turn
        # call the aq command
        python_path = os.path.dirname(sys.executable)
        newenv = {}
        newenv["USER"] = os.environ.get('USER', '')
        if env:
            for (key, value) in env.iteritems():
                newenv[key] = value
        if "PATH" in newenv:
            newenv["PATH"] = "%s:%s:%s" % (git_path, python_path, newenv["PATH"])
        else:
            newenv["PATH"] = "%s:%s:%s" % (git_path, python_path, '/bin:/usr/bin')
        return newenv

    def gitcommand_raw(self, command, **kwargs):
        if isinstance(command, list):
            args = command[:]
        else:
            args = [command]
        args.insert(0, "git")
        env = self.gitenv(kwargs.pop("env", None))
        p = Popen(args, stdout=PIPE, stderr=PIPE, env=env, **kwargs)
        return p

    def gitcommand(self, command, **kwargs):
        p = self.gitcommand_raw(command, **kwargs)
        # Ignore out/err unless we get a non-zero return code, then log it.
        (out, err) = p.communicate()
        self.assertEqual(p.returncode, 0,
                         "Non-zero return code for %s, "
                         "STDOUT:\n@@@\n'%s'\n@@@\n"
                         "STDERR:\n@@@\n'%s'\n@@@\n"
                         % (command, out, err))
        return (out, err)

    def gitcommand_expectfailure(self, command, **kwargs):
        p = self.gitcommand_raw(command, **kwargs)
        # Ignore out/err unless we get a non-zero return code, then log it.
        (out, err) = p.communicate()
        self.failIfEqual(p.returncode, 0,
                         "Zero return code for %s, "
                         "STDOUT:\n@@@\n'%s'\n@@@\n"
                         "STDERR:\n@@@\n'%s'\n@@@\n"
                         % (command, out, err))
        return (out, err)

    def check_git_merge_health(self, repo):
        command = "merge HEAD"
        out = self.gitcommand(command.split(" "), cwd=repo)
        return

    def grepcommand(self, command, **kwargs):
        if self.config.has_option("unittest", "grep"):
            grep = self.config.get("unittest", "grep")
        else:
            grep = "/bin/grep"
        if isinstance(command, list):
            args = command[:]
        else:
            args = [command]
        args.insert(0, grep)
        env = {}
        p = Popen(args, stdout=PIPE, stderr=PIPE, **kwargs)
        (out, err) = p.communicate()
        # Ignore out/err unless we get a non-zero return code, then log it.
        if p.returncode == 0:
            return out.splitlines()
        if p.returncode == 1:
            return []
        self.fail("Error return code for %s, "
                  "STDOUT:\n@@@\n'%s'\n@@@\nSTDERR:\n@@@\n'%s'\n@@@\n"
                  % (command, out, err))

    def findcommand(self, command, **kwargs):
        if self.config.has_option("unittest", "find"):
            find = self.config.get("unittest", "find")
        else:
            find = "/usr/bin/find"
        if isinstance(command, list):
            args = command[:]
        else:
            args = [command]
        args.insert(0, find)
        env = {}
        p = Popen(args, stdout=PIPE, stderr=PIPE, **kwargs)
        (out, err) = p.communicate()
        # Ignore out/err unless we get a non-zero return code, then log it.
        if p.returncode == 0:
            return out.splitlines()
        self.fail("Error return code for %s, "
                  "STDOUT:\n@@@\n'%s'\n@@@\nSTDERR:\n@@@\n'%s'\n@@@\n"
                  % (command, out, err))

    def writescratch(self, filename, contents):
        scratchfile = os.path.join(self.scratchdir, filename)
        with open(scratchfile, 'w') as f:
            f.write(contents)
        return scratchfile

    def readscratch(self, filename):
        scratchfile = os.path.join(self.scratchdir, filename)
        with open(scratchfile, 'r') as f:
            contents = f.read()
        return contents

    def dsdb_expect(self, command, fail=False, errstr=""):
        if fail:
            filename = DSDB_EXPECT_FAILURE_FILE
        else:
            filename = DSDB_EXPECT_SUCCESS_FILE

        expected_name = os.path.join(self.dsdb_coverage_dir, filename)
        with open(expected_name, "a") as fp:
            if isinstance(command, list):
                fp.write(" ".join([str(cmd) for cmd in command]))
            else:
                fp.write(str(command))
            fp.write("\n")
        if fail and errstr:
            errfile = DSDB_EXPECT_FAILURE_ERROR
            expected_name = os.path.join(self.dsdb_coverage_dir, errfile)
            with open(expected_name, "a") as fp:
                fp.write(errstr)
                fp.write("\n")

    def dsdb_expect_add(self, hostname, ip, interface=None, mac=None,
                        primary=None, comments=None, fail=False):
        command = ["add_host", "-host_name", hostname,
                   "-ip_address", str(ip), "-status", "aq"]
        if interface:
            command.extend(["-interface_name",
                            str(interface).replace('/', '_')])
        if mac:
            command.extend(["-ethernet_address", str(mac)])
        if primary:
            command.extend(["-primary_host_name", primary])
        if comments:
            command.extend(["-comments", comments])

        self.dsdb_expect(" ".join(command), fail=fail)

    def dsdb_expect_delete(self, ip, fail=False):
        self.dsdb_expect("delete_host -ip_address %s" % ip, fail=fail)

    def dsdb_expect_update(self, fqdn, iface=None, ip=None, mac=None,
                           comments=None, fail=False):
        command = ["update_aqd_host", "-host_name", fqdn]
        if iface:
            command.extend(["-interface_name", iface])
        if ip:
            command.extend(["-ip_address", str(ip)])
        if mac:
            command.extend(["-ethernet_address", str(mac)])
        if comments:
            command.extend(["-comments", comments])
        self.dsdb_expect(" ".join(command), fail=fail)

    def dsdb_expect_rename(self, fqdn, new_fqdn=None, iface=None,
                           new_iface=None, fail=False):
        command = ["update_aqd_host", "-host_name", fqdn]
        if new_fqdn:
            command.extend(["-primary_host_name", new_fqdn])
        if iface:
            command.extend(["-interface_name", iface])
        if new_iface:
            command.extend(["-new_interface_name", new_iface])
        self.dsdb_expect(" ".join(command), fail=fail)

    def dsdb_expect_add_campus(self, campus, comments=None, fail=False,
                               errstr=""):
        command = ["add_campus_aq", "-campus_name", campus]
        if comments:
            command.extend(["-comments", comments])
        self.dsdb_expect(" ".join(command), fail=fail, errstr=errstr)

    def dsdb_expect_del_campus(self, campus, fail=False, errstr=""):
        command = ["delete_campus_aq", "-campus", campus]
        self.dsdb_expect(" ".join(command), fail=fail, errstr=errstr)

    def dsdb_expect_add_campus_building(self, campus, building, fail=False,
                                        errstr=""):
        command = ["add_campus_building_aq", "-campus_name", campus,
                   "-building_name", building]
        self.dsdb_expect(" ".join(command), fail=fail, errstr=errstr)

    def dsdb_expect_del_campus_building(self, campus, building, fail=False,
                                        errstr=""):
        command = ["delete_campus_building_aq", "-campus_name", campus,
                   "-building_name", building]
        self.dsdb_expect(" ".join(command), fail=fail, errstr=errstr)

    def dsdb_verify(self, empty=False):
        fail_expected_name = os.path.join(self.dsdb_coverage_dir,
                                          DSDB_EXPECT_FAILURE_FILE)
        issued_name = os.path.join(self.dsdb_coverage_dir, DSDB_ISSUED_CMDS_FILE)

        expected = {}
        for filename in [DSDB_EXPECT_SUCCESS_FILE, DSDB_EXPECT_FAILURE_FILE]:
            expected_name = os.path.join(self.dsdb_coverage_dir, filename)
            try:
                with open(expected_name, "r") as fp:
                    for line in fp:
                        expected[line.rstrip("\n")] = True
            except IOError:
                pass

        # This is likely a logic error in the test
        if not expected and not empty:
            self.fail("dsdb_verify() called when no DSDB commands were "
                      "expected?!?")

        issued = {}
        try:
            with open(issued_name, "r") as fp:
                for line in fp:
                    issued[line.rstrip("\n")] = True
        except IOError:
            pass

        errors = []
        for cmd, dummy in expected.items():
            if cmd not in issued:
                errors.append("'%s'" % cmd)
        # Unexpected DSDB commands are caught by the fake_dsdb script

        if errors:
            self.fail("The following expected DSDB commands were not called:"
                      "\n@@@\n%s\n@@@\n" % "\n".join(errors))

    def verify_buildfiles(self, domain, object,
                          want_exist=True, command='manage'):
        qdir = self.config.get('broker', 'quattordir')
        domaindir = os.path.join(qdir, 'build', 'xml', domain)
        xmlfile = os.path.join(domaindir, object + self.profile_suffix)
        depfile = os.path.join(domaindir, object + '.dep')
        profile = self.build_profile_name(object, domain=domain)
        for f in [xmlfile, depfile, profile]:
            if want_exist:
                self.failUnless(os.path.exists(f),
                                "Expecting %s to exist before running %s." %
                                (f, command))
            else:
                self.failIf(os.path.exists(f),
                            "Not expecting %s to exist after running %s." %
                            (f, command))

    def demote_current_user(self, role="nobody"):
        principal = self.config.get('unittest', 'principal')
        command = ["permission", "--role", role, "--principal", principal]
        self.noouttest(command)

    def promote_current_user(self):
        srcdir = self.config.get("broker", "srcdir")
        add_admin = os.path.join(srcdir, "tests", "aqdb", "add_admin.py")
        env = os.environ.copy()
        env['AQDCONF'] = self.config.baseconfig
        p = Popen([add_admin], stdout=PIPE, stderr=PIPE, env=env)
        (out, err) = p.communicate()
        self.assertEqual(p.returncode, 0,
                         "Failed to restore admin privs '%s', '%s'." %
                         (out, err))
