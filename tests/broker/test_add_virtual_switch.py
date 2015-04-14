#!/usr/bin/env python
# -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# ex: set expandtab softtabstop=4 shiftwidth=4:
#
# Copyright (C) 2014,2015  Contributor
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
"""Module for testing the add network device command."""

if __name__ == "__main__":
    import utils
    utils.import_depends()

import unittest2 as unittest
from brokertest import TestBrokerCommand


class TestAddVirtualSwitch(TestBrokerCommand):
    def test_100_add_utvswitch(self):
        self.check_plenary_gone("virtualswitchdata", "utvswitch")
        command = ["add_virtual_switch", "--virtual_switch", "utvswitch"]
        self.noouttest(command)
        self.check_plenary_exists("virtualswitchdata", "utvswitch")

    def test_105_cat_utvswitch(self):
        command = ["cat", "--virtual_switch", "utvswitch", "--data"]
        out = self.commandtest(command)
        self.matchclean(out, "system/virtual_switch/port_groups", command)

    def test_110_bind_portgroup(self):
        net = self.net["autopg1"]
        command = ["bind_port_group", "--virtual_switch", "utvswitch",
                   "--networkip", net.ip, "--type", "user", "--tag", "710"]
        self.noouttest(command)

    def test_115_show_utvswitch(self):
        net = self.net["autopg1"]
        command = ["show_virtual_switch", "--virtual_switch", "utvswitch"]
        out = self.commandtest(command)
        self.matchoutput(out, "Virtual Switch: utvswitch", command)
        self.matchoutput(out, "Port Group: user-v710", command)
        self.matchoutput(out, "Network: %s" % net.ip, command)
        self.matchclean(out, "Comments", command)

    def test_115_show_utvswitch_proto(self):
        net = self.net["autopg1"]
        command = ["show_virtual_switch", "--virtual_switch", "utvswitch",
                   "--format", "proto"]
        vswitch = self.protobuftest(command, expect=1)[0]
        self.assertEqual(vswitch.name, "utvswitch")
        self.assertEqual(len(vswitch.portgroups), 1)
        self.assertEqual(vswitch.portgroups[0].ip, str(net.ip))
        self.assertEqual(vswitch.portgroups[0].cidr, 29)
        self.assertEqual(vswitch.portgroups[0].network_tag, 710)
        self.assertEqual(vswitch.portgroups[0].usage, "user")

    def test_115_cat_utvswitch(self):
        net = self.net["autopg1"]
        command = ["cat", "--virtual_switch", "utvswitch", "--data"]
        out = self.commandtest(command)
        self.searchoutput(out,
                          r'"system/virtual_switch/port_groups/{user-v710}" = nlist\(\s*'
                          r'"netmask", "%s",\s*'
                          r'"network_environment", "internal",\s*'
                          r'"network_ip", "%s",\s*'
                          r'"network_tag", 710,\s*'
                          r'"network_type", "%s",\s*'
                          r'"usage", "user"\s*\);' %
                          (net.netmask, net.ip, net.nettype),
                          command)

    def test_120_add_utvswitch2(self):
        self.noouttest(["add_virtual_switch", "--virtual_switc", "utvswitch2",
                        "--comments", "Some virtual switch comments"])

    def test_125_verify_utvswitch2(self):
        command = ["show_virtual_switch", "--virtual_switch", "utvswitch2"]
        out = self.commandtest(command)
        self.matchoutput(out, "Virtual Switch: utvswitch2", command)
        self.matchoutput(out, "Comments: Some virtual switch comments", command)
        self.matchclean(out, "Port Group", command)

    def test_125_verify_all(self):
        command = ["show_virtual_switch", "--all"]
        out = self.commandtest(command)
        self.searchoutput(out, "^utvswitch$", command)
        self.searchoutput(out, "^utvswitch2$", command)

    def test_125_verify_all_proto(self):
        command = ["show_virtual_switch", "--all", "--format", "proto"]
        vswitches = self.protobuftest(command)
        vswitch_names = set([msg.name for msg in vswitches])
        for vswitch_name in ("utvswitch", "utvswitch2"):
            self.assertTrue(vswitch_name in vswitch_names)

    def test_130_add_camelcase(self):
        self.noouttest(["add_virtual_switch", "--virtual_switch", "CaMeLcAsE"])
        self.check_plenary_exists("virtualswitchdata", "camelcase")
        self.check_plenary_gone("virtualswitchdata", "CaMeLcAsE")

    def test_200_add_utvswitch_again(self):
        command = ["add_virtual_switch", "--virtual_switch", "utvswitch"]
        out = self.badrequesttest(command)
        self.matchoutput(out, "Virtual Switch utvswitch already exists.",
                         command)

    def test_200_bad_name(self):
        command = ["add_virtual_switch", "--virtual_switch", "oops@!"]
        out = self.badrequesttest(command)
        self.matchoutput(out,
                         "'oops@!' is not a valid value for --virtual_switch.",
                         command)

    def test_200_bind_again(self):
        net = self.net["autopg1"]
        command = ["bind_port_group", "--virtual_switch", "utvswitch",
                   "--networkip", net.ip, "--type", "user", "--tag", "710"]
        out = self.badrequesttest(command)
        self.matchoutput(out, "Port Group user-v710 is already bound to "
                         "virtual switch utvswitch.", command)

    def test_200_bind_different_type(self):
        net = self.net["autopg1"]
        command = ["bind_port_group", "--virtual_switch", "utvswitch2",
                   "--networkip", net.ip, "--type", "vcs", "--tag", "710"]
        out = self.badrequesttest(command)
        self.matchoutput(out, "Port Group user-v710 is already used as "
                         "type user.", command)

    def test_200_bind_different_tag(self):
        net = self.net["autopg1"]
        command = ["bind_port_group", "--virtual_switch", "utvswitch2",
                   "--networkip", net.ip, "--type", "user", "--tag", "711"]
        out = self.badrequesttest(command)
        self.matchoutput(out, "Port Group user-v710 is already tagged as 710.",
                         command)

    def test_200_bind_duplicate_tag(self):
        net = self.net["autopg2"]
        command = ["bind_port_group", "--virtual_switch", "utvswitch",
                   "--networkip", net.ip, "--type", "user", "--tag", "710"]
        out = self.badrequesttest(command)
        self.matchoutput(out,
                         "Virtual Switch utvswitch already has a port group "
                         "with tag 710.",
                         command)

    def test_300_update_utvswitch2(self):
        self.noouttest(["update_virtual_switch",
                        "--virtual_switch", "utvswitch2",
                        "--comments", "Some other vswitch comments"])

    def test_305_verify_update_utvswitch2(self):
        command = ["show_virtual_switch", "--virtual_switch", "utvswitch2"]
        out = self.commandtest(command)
        self.matchoutput(out, "Virtual Switch: utvswitch2", command)
        self.matchoutput(out, "Comments: Some other vswitch comments", command)
        self.matchclean(out, "Port Group", command)

    def test_310_clear_comments(self):
        self.noouttest(["update_virtual_switch",
                        "--virtual_switch", "utvswitch2", "--comments", ""])

    def test_315_verify_clear_comments(self):
        command = ["show_virtual_switch", "--virtual_switch", "utvswitch2"]
        out = self.commandtest(command)
        self.matchclean(out, "Comments", command)

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAddVirtualSwitch)
    unittest.TextTestRunner(verbosity=2).run(suite)
