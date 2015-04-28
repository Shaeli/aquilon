# -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# ex: set expandtab softtabstop=4 shiftwidth=4:
#
# Copyright (C) 2008,2009,2010,2011,2013,2014  Contributor
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
"""Contains the logic for `aq compile`."""

from sqlalchemy.orm import joinedload, subqueryload
from sqlalchemy.sql import and_

from aquilon.aqdb.model import (Personality, Host, Cluster, CompileableMixin,
                                ServiceInstance)
from aquilon.worker.broker import BrokerCommand  # pylint: disable=W0611
from aquilon.worker.dbwrappers.branch import get_branch_and_author
from aquilon.worker.locks import CompileKey
from aquilon.worker.templates import Plenary, PlenaryCollection
from aquilon.worker.templates.domain import TemplateDomain


class CommandCompile(BrokerCommand):

    required_parameters = []
    requires_readonly = True

    def render(self, session, logger, domain, sandbox,
               pancinclude, pancexclude, pancdebug, cleandeps,
               **arguments):
        dbdomain, dbauthor = get_branch_and_author(session, domain=domain,
                                                   sandbox=sandbox, compel=True)

        # Grab a shared lock on personalities and services used by the domain.
        # Object templates (hosts, clusters) are protected by the domain lock.
        plenaries = PlenaryCollection(logger=logger)

        for cls_ in CompileableMixin.__subclasses__():
            q = session.query(Personality)
            q = q.join(cls_)
            q = q.filter(and_(cls_.branch == dbdomain,
                              cls_.sandbox_author == dbauthor))
            q = q.reset_joinpoint()
            q = q.options(joinedload('paramholder'),
                          subqueryload('paramholder.parameters'))

            for dbpers in q:
                plenaries.append(Plenary.get_plenary(dbpers))

        q1 = session.query(ServiceInstance)
        q1 = q1.join(ServiceInstance.clients)
        q1 = q1.filter(and_(Host.branch == dbdomain,
                            Host.sandbox_author == dbauthor))

        q2 = session.query(ServiceInstance)
        q2 = q2.join(ServiceInstance.cluster_clients)
        q2 = q2.filter(and_(Cluster.branch == dbdomain,
                            Cluster.sandbox_author == dbauthor))

        plenaries.extend(map(Plenary.get_plenary, q1.union(q2)))

        if pancdebug:
            pancinclude = r'.*'
            pancexclude = r'components/spma/functions'
        dom = TemplateDomain(dbdomain, dbauthor, logger=logger)
        with CompileKey.merge([CompileKey(domain=dbdomain.name, logger=logger),
                               plenaries.get_key(exclusive=False)]):
            dom.compile(session,
                        panc_debug_include=pancinclude,
                        panc_debug_exclude=pancexclude,
                        cleandeps=cleandeps,
                        locked=True)
        return
