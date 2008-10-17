#!/ms/dist/python/PROJ/core/2.5.0/bin/python
# ex: set expandtab softtabstop=4 shiftwidth=4: -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# Copyright (C) 2008 Morgan Stanley
#
# This module is part of Aquilon
"""Contains the logic for `aq search host`."""


from aquilon.server.broker import (format_results, add_transaction, az_check,
                                   BrokerCommand)
from aquilon.server.formats.system import SimpleSystemList
from aquilon.aqdb.sy.host import Host
from aquilon.aqdb.cfg.cfg_path import CfgPath
from aquilon.server.dbwrappers.system import search_system_query
from aquilon.server.dbwrappers.domain import get_domain
from aquilon.server.dbwrappers.status import get_status
from aquilon.server.dbwrappers.machine import get_machine
from aquilon.server.dbwrappers.archetype import get_archetype
from aquilon.server.dbwrappers.cfg_path import get_cfg_path
from aquilon.server.dbwrappers.service import get_service
from aquilon.server.dbwrappers.service_instance import get_service_instance


class CommandSearchHost(BrokerCommand):

    required_parameters = []

    @add_transaction
    @az_check
    @format_results
    def render(self, session, hostname, machine, domain, archetype,
               buildstatus, personality, os, service, instance,
               fullinfo, **arguments):
        if hostname:
            arguments['fqdn'] = hostname
        q = search_system_query(session, Host, **arguments)
        if machine:
            dbmachine = get_machine(session, machine)
            q = q.filter_by(machine=dbmachine)
        if domain:
            dbdomain = get_domain(session, domain)
            q = q.filter_by(domain=dbdomain)
        if archetype:
            dbarchetype = get_archetype(session, archetype)
            q = q.filter_by(archetype=dbarchetype)
        if buildstatus:
            dbbuildstatus = get_status(session, buildstatus)
            q = q.filter_by(status=dbbuildstatus)
        if personality:
            dbpersonality = get_cfg_path(session, "personality", personality)
            q = q.join('build_items').filter_by(cfg_path=dbpersonality)
            q = q.reset_joinpoint()
        if os:
            dbos = get_cfg_path(session, "os", os)
            q = q.join('build_items').filter_by(cfg_path=dbos)
            q = q.reset_joinpoint()
        if service:
            dbservice = get_service(session, service)
            if instance:
                dbsi = get_service_instance(session, dbservice, instance)
                q = q.join('build_items')
                q = q.filter_by(cfg_path=dbsi.cfg_path)
                q = q.reset_joinpoint()
            else:
                q = q.join('build_items')
                path_query = dbservice.cfg_path.relative_path + '/%'
                q = q.filter(CfgPath.relative_path.like(path_query))
                q = q.reset_joinpoint()
                q = q.join(['build_items', 'cfg_path'])
                q = q.filter_by(tld=dbservice.cfg_path.tld)
                q = q.reset_joinpoint()
        elif instance:
            q = q.join('build_items')
            path_query = '%/' + instance.lower().strip()
            q = q.filter(CfgPath.relative_path.like(path_query))
            q = q.reset_joinpoint()
            q = q.join(['build_items', 'cfg_path', 'tld'])
            q = q.filter_by(type='service')
            q = q.reset_joinpoint()
        if fullinfo:
            return q.all()
        return SimpleSystemList(q.all())


#if __name__=='__main__':
