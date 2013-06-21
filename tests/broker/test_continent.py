#!/usr/bin/env python2.6
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
"""Module for testing the add/del/show continent command."""

import unittest

if __name__ == "__main__":
    import utils
    utils.import_depends()

from brokertest import TestBrokerCommand

continents = {'af': ('Africa', 'ln'),
              'as': ('Asia', 'hk'),
              'au': ('Australia', 'hk'),
              'eu': ('Europe', 'ln'),
              'na': ('North America', 'ny'),
              'sa': ('South America', 'ny')}


class TestContinent(TestBrokerCommand):
    def test_add_continents(self):
        for continent, params in continents.items():
            self.noouttest(["add_continent", "--continent", continent,
                            "--fullname", params[0], "--hub", params[1]])


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestContinent)
    unittest.TextTestRunner(verbosity=2).run(suite)
