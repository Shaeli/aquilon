# -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# ex: set expandtab softtabstop=4 shiftwidth=4:
#
# Copyright (C) 2009,2010,2011,2012,2013,2014,2015,2016,2017  Contributor
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
"""Contains the logic for `aq del allowed personality --cluster`."""

from aquilon.exceptions_ import ArgumentError
from aquilon.aqdb.model import Personality, Cluster, MetaCluster
from aquilon.worker.broker import BrokerCommand
from aquilon.worker.dbwrappers.change_management import ChangeManagement


class CommandDelAllowedPersonalityCluster(BrokerCommand):
    requires_plenaries = True

    required_parameters = ["archetype", "personality", "cluster"]

    def render(self, session, plenaries, archetype, personality, cluster,
               metacluster, user, justification, reason, logger, **arguments):
        dbpers = Personality.get_unique(session, name=personality,
                                        archetype=archetype, compel=True)
        if cluster:
            dbclus = Cluster.get_unique(session, cluster, compel=True)
            if isinstance(dbclus, MetaCluster):
                raise ArgumentError("Please use --metacluster for metaclusters.")
        else:
            dbclus = MetaCluster.get_unique(session, metacluster, compel=True)

        # Validate ChangeManagement
        cm = ChangeManagement(session, user, justification, reason, logger, self.command, **arguments)
        cm.consider(dbclus)
        cm.validate()

        plenaries.add(dbclus)

        if len(dbclus.allowed_personalities) > 1:
            members = dbclus.hosts[:]
            if hasattr(dbclus, 'members'):
                members.extend(dbclus.members)

            for obj in members:
                if obj.personality == dbpers:
                    raise ArgumentError("Member {0:l} has {1:l}, which is "
                                        "incompatible with this constraint."
                                        .format(obj, obj.personality))

        if dbpers in dbclus.allowed_personalities:
            dbclus.allowed_personalities.remove(dbpers)

        session.flush()

        plenaries.write()

        return
