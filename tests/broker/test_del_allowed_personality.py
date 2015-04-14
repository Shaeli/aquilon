#!/usr/bin/env python
# -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# ex: set expandtab softtabstop=4 shiftwidth=4:
#
# Copyright (C) 2011,2012,2013,2014,2015  Contributor
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
"""Module for testing the del allowed_personality commands."""

if __name__ == "__main__":
    import utils
    utils.import_depends()

import unittest2 as unittest
from brokertest import TestBrokerCommand


class TestDelAllowedPersonality(TestBrokerCommand):

    def test_10_delbadconstraint(self):
        command = ["del_allowed_personality", "--archetype", "vmhost",
                   "--personality=vulcan-10g-server-prod", "--cluster=utecl1"]
        out = self.badrequesttest(command)
        self.matchoutput(out,
                         "Member host evh1.aqd-unittest.ms.com has personality "
                         "vmhost/vulcan-10g-server-prod, which is incompatible "
                         "with this constraint.",
                         command)

    def test_12_failmissingcluster(self):
        command = ["del_allowed_personality", "--archetype", "vmhost",
                   "--personality=vulcan-10g-server-prod", "--cluster=does-not-exist"]
        out = self.notfoundtest(command)
        self.matchoutput(out, "Cluster does-not-exist not found.", command)

    def test_14_failmissingcluster(self):
        command = ["del_allowed_personality", "--archetype", "vmhost",
                   "--personality=does-not-exist", "--cluster=utecl1"]
        out = self.notfoundtest(command)
        self.matchoutput(out, "Personality does-not-exist, "
                              "archetype vmhost not found.",
                         command)

    def test_15_delconstraint(self):
        self.noouttest(["del_allowed_personality", "--archetype", "vmhost",
                        "--personality=generic", "--cluster=utecl1"])

    def test_17_delconstraint(self):
        self.noouttest(["del_allowed_personality", "--archetype", "vmhost",
                        "--personality=generic", "--cluster=utecl1"])

    def test_20_checkconstraint(self):
        command = ["show_cluster", "--cluster=utecl1"]
        out = self.commandtest(command)
        self.matchoutput(out, "Allowed Personality: Personality vmhost/vulcan-10g-server-prod", command)
        self.matchclean(out, "Allowed Personality: Personality vmhost/generic", command)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDelAllowedPersonality)
    unittest.TextTestRunner(verbosity=2).run(suite)
