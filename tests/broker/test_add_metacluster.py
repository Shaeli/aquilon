#!/usr/bin/env python
# -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# ex: set expandtab softtabstop=4 shiftwidth=4:
#
# Copyright (C) 2009,2010,2011,2012,2013,2014,2015  Contributor
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
"""Module for testing the add metacluster command."""

if __name__ == "__main__":
    import utils
    utils.import_depends()

import unittest2 as unittest
from brokertest import TestBrokerCommand
from personalitytest import PersonalityTestMixin


class TestAddMetaCluster(PersonalityTestMixin, TestBrokerCommand):

    def test_000_add_personality(self):
        # The broker currently assumes this personality to exist
        self.create_personality("metacluster", "metacluster",
                                grn="grn:/ms/ei/aquilon/aqd")

    def test_100_add_utmc1(self):
        command = ["add_metacluster", "--metacluster=utmc1",
                   "--domain=unittest", "--building=ut"]
        self.noouttest(command)

    def test_105_show_utmc1(self):
        command = "show metacluster --metacluster utmc1"
        out = self.commandtest(command.split(" "))
        default_members = self.config.getint("archetype_metacluster",
                                             "max_members_default")
        self.matchoutput(out, "MetaCluster: utmc1", command)
        self.matchoutput(out, "Max members: %s" % default_members, command)
        self.matchclean(out, "Comments", command)
        self.matchclean(out, "Member:", command)
        self.matchclean(out, "Share:", command)
        self.matchoutput(out, "Domain: unittest", command)
        self.matchoutput(out, "Build Status: build", command)

    def test_105_show_utmc1_proto(self):
        command = "show metacluster --metacluster utmc1 --format proto"
        mc = self.protobuftest(command.split(" "), expect=1)[0]
        default_members = self.config.getint("archetype_metacluster",
                                             "max_members_default")
        self.assertEqual(mc.name, "utmc1")
        self.assertEqual(mc.max_members, default_members)
        self.assertEqual(mc.domain.name, "unittest")
        self.assertEqual(mc.domain.type, mc.domain.DOMAIN)
        self.assertEqual(mc.sandbox_author, "")
        self.assertEqual(mc.personality.archetype.name, "metacluster")
        self.assertEqual(mc.personality.name, "metacluster")
        self.assertEqual(mc.status, "build")
        self.assertEqual(mc.virtual_switch.name, "")

    def test_110_add_utmc2(self):
        command = ["add_metacluster", "--metacluster=utmc2",
                   "--max_members=99", "--building=ut",
                   "--domain=unittest",
                   "--comments", "Some metacluster comments"]
        self.noouttest(command)

    def test_115_show_utmc2(self):
        command = "show metacluster --metacluster utmc2"
        out = self.commandtest(command.split(" "))
        self.matchoutput(out, "MetaCluster: utmc2", command)
        self.matchoutput(out, "Max members: 99", command)
        self.matchoutput(out, "Comments: Some metacluster comments", command)

    def test_115_show_utmc2_proto(self):
        command = "show metacluster --metacluster utmc2 --format proto"
        mc = self.protobuftest(command.split(" "), expect=1)[0]
        self.assertEqual(mc.max_members, 99)
        self.assertEqual(mc.location_constraint.name, "ut")
        self.assertEqual(mc.location_constraint.location_type, "building")

    def test_120_add_utmc3(self):
        command = ["add_metacluster", "--metacluster=utmc3",
                   "--max_members=0", "--building=ut", "--domain=unittest",
                   "--comments", "MetaCluster with no members allowed"]
        self.noouttest(command)

    def test_125_show_utmc3(self):
        command = "show metacluster --metacluster utmc3"
        out = self.commandtest(command.split(" "))
        self.matchoutput(out, "MetaCluster: utmc3", command)
        self.matchoutput(out, "Max members: 0", command)
        self.matchoutput(out, "Comments: MetaCluster with no members allowed",
                         command)

    def test_130_add_utmc4(self):
        # Sort of a mini-10 Gig design for port group testing...
        command = ["add_metacluster", "--metacluster=utmc4",
                   "--max_members=6", "--building=ut",
                   "--domain=unittest"]
        self.noouttest(command)

    def test_140_add_utmc7(self):
        # Test moving machines between metaclusters
        command = ["add_metacluster", "--metacluster=utmc7", "--building=ut",
                   "--domain=unittest"]
        self.noouttest(command)

    def test_150_add_sandboxmc(self):
        # Test moving machines between metaclusters
        command = ["add_metacluster", "--metacluster=sandboxmc", "--building=ut",
                   "--sandbox=%s/utsandbox" % self.user]
        self.noouttest(command)

    def test_160_add_vulcan1(self):
        # this should be removed when virtbuild supports new options
        command = ["add_metacluster", "--metacluster=vulcan1"]
        self.noouttest(command)

    def test_200_add_utmc1_again(self):
        command = ["add_metacluster", "--metacluster=utmc1",
                   "--building=ut", "--domain=unittest"]
        out = self.badrequesttest(command)
        self.matchoutput(out, "Metacluster utmc1 already exists.", command)

    def test_200_nonexistant(self):
        command = "show metacluster --metacluster metacluster-does-not-exist"
        self.notfoundtest(command.split(" "))

    def test_200_global_name(self):
        command = ["add_metacluster", "--metacluster=global", "--building=ut",
                   "--domain=unittest"]
        out = self.badrequesttest(command)
        self.matchoutput(out, "name global is reserved", command)

    def test_300_show_all(self):
        command = "show metacluster --all"
        out = self.commandtest(command.split(" "))
        self.matchoutput(out, "utmc1", command)
        self.matchoutput(out, "utmc2", command)
        self.matchoutput(out, "utmc3", command)

    def test_300_show_all_proto(self):
        command = "show metacluster --all --format proto"
        mcs = self.protobuftest(command.split(" "))
        names = set([msg.name for msg in mcs])
        for name in ("utmc1", "utmc2", "utmc3"):
            self.assertTrue(name in names)

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAddMetaCluster)
    unittest.TextTestRunner(verbosity=2).run(suite)
