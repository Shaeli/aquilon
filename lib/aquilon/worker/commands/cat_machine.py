# -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# ex: set expandtab softtabstop=4 shiftwidth=4:
#
# Copyright (C) 2008,2009,2010,2011,2013,2015,2016  Contributor
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
"""Contains the logic for `aq cat --machine`."""

from aquilon.aqdb.model import Machine
from aquilon.worker.broker import BrokerCommand
from aquilon.worker.templates import Plenary


class CommandCatMachine(BrokerCommand):

    required_parameters = ["machine"]

    # We do not lock the plenary while reading it
    _is_lock_free = True

    def render(self, session, logger, machine, generate, **_):
        dbmachine = Machine.get_unique(session, machine, compel=True)
        plenary_info = Plenary.get_plenary(dbmachine, logger=logger)

        if generate:
            return plenary_info._generate_content()
        else:
            return plenary_info.read()
