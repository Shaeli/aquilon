# ex: set expandtab softtabstop=4 shiftwidth=4: -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2008,2009,2010  Contributor
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the EU DataGrid Software License.  You should
# have received a copy of the license with this program, and the
# license is published at
# http://eu-datagrid.web.cern.ch/eu-datagrid/license.html.
#
# THE FOLLOWING DISCLAIMER APPLIES TO ALL SOFTWARE CODE AND OTHER
# MATERIALS CONTRIBUTED IN CONNECTION WITH THIS PROGRAM.
#
# THIS SOFTWARE IS LICENSED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE AND ANY WARRANTY OF NON-INFRINGEMENT, ARE
# DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
# OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT
# OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE. THIS
# SOFTWARE MAY BE REDISTRIBUTED TO OTHERS ONLY BY EFFECTIVELY USING
# THIS OR ANOTHER EQUIVALENT DISCLAIMER AS WELL AS ANY OTHER LICENSE
# TERMS THAT MAY APPLY.
"""Contains the logic for `aq search host`."""


from sqlalchemy.orm import aliased

from aquilon.exceptions_ import ArgumentError
from aquilon.server.broker import BrokerCommand
from aquilon.server.formats.system import SimpleSystemList
from aquilon.aqdb.model import (Host, Cluster, Domain, Archetype, Personality,
                                HostLifecycle, OperatingSystem, Service,
                                ServiceInstance, NasDisk, Disk, Machine, Model,
                                System, DnsDomain, Interface, HardwareEntity,
                                VlanInterface, AddressAssignment)
from aquilon.aqdb.model.dns_domain import parse_fqdn
from aquilon.server.dbwrappers.hardware_entity import search_hardware_entity_query
from aquilon.server.dbwrappers.service_instance import get_service_instance
from aquilon.server.dbwrappers.branch import get_branch_and_author
from aquilon.server.dbwrappers.location import get_location
from aquilon.server.dbwrappers.network import get_network_byip


class CommandSearchHost(BrokerCommand):

    required_parameters = []

    def render(self, session, logger, hostname, machine, archetype,
               buildstatus, personality, osname, osversion, service, instance,
               model, machine_type, vendor, serial, cluster,
               guest_on_cluster, guest_on_share,
               domain, sandbox, branch,
               dns_domain, shortname, mac, ip, networkip,
               exact_location, fullinfo, **arguments):
        dnsq = session.query(System.ip)
        use_dnsq = False
        if hostname:
            (short, dbdns_domain) = parse_fqdn(session, hostname)
            dnsq = dnsq.filter_by(name=short)
            dnsq = dnsq.filter_by(dns_domain=dbdns_domain)
            use_dnsq = True
        if dns_domain:
            dbdns_domain = DnsDomain.get_unique(session, dns_domain, compel=True)
            dnsq = dnsq.filter_by(dns_domain=dbdns_domain)
            use_dnsq = True
        if shortname:
            dnsq = dnsq.filter_by(name=shortname)
            use_dnsq = True

        use_addrq = False
        addrq = session.query(Interface.id)
        if mac:
            addrq = addrq.filter(Interface.mac == mac)
            use_addrq = True
        addrq = addrq.join(VlanInterface, AddressAssignment)
        if ip:
            addrq = addrq.filter_by(ip=ip)
            use_addrq = True
        if networkip:
            dbnetwork = get_network_byip(session, networkip)
            addrq = addrq.filter(AddressAssignment.ip > dbnetwork.network.ip)
            addrq = addrq.filter(AddressAssignment.ip < dbnetwork.network.broadcast)
            use_addrq = True
        if use_dnsq:
            addrq = addrq.filter(AddressAssignment.ip.in_(dnsq.subquery()))
            use_addrq = True

        q = session.query(Host)
        if use_addrq:
            q = q.join(HardwareEntity, Interface)
            q = q.filter(Interface.id.in_(addrq.subquery()))
            q = q.reset_joinpoint()

        dblocation = get_location(session, **arguments)
        if dblocation:
            q = q.join(HardwareEntity)
            if exact_location:
                q = q.filter_by(location=dblocation)
            else:
                childids = dblocation.offspring_ids()
                q = q.filter(HardwareEntity.location_id.in_(childids))
            q = q.reset_joinpoint()

        if model or vendor or machine_type:
            q = q.join(HardwareEntity)
            subq = Model.get_matching_query(session, name=model, vendor=vendor,
                                            machine_type=machine_type,
                                            compel=True)
            q = q.filter(HardwareEntity.model_id.in_(subq))
            q = q.reset_joinpoint()

        if serial:
            q = q.join(HardwareEntity)
            q = q.filter_by(serial_no=serial)
            q = q.reset_joinpoint()

        if machine:
            dbmachine = Machine.get_unique(session, machine, compel=True)
            q = q.filter_by(hardware_entity=dbmachine)

        (dbbranch, dbauthor) = get_branch_and_author(session, logger,
                                                     domain=domain,
                                                     sandbox=sandbox,
                                                     branch=branch)
        if dbbranch:
            q = q.filter_by(branch=dbbranch)
        if dbauthor:
            q = q.filter_by(sandbox_author=dbauthor)

        if archetype:
            # Added to the searches as appropriate below.
            dbarchetype = Archetype.get_unique(session, archetype, compel=True)
        if personality and archetype:
            dbpersonality = Personality.get_unique(session,
                                                   archetype=dbarchetype,
                                                   name=personality,
                                                   compel=True)
            q = q.filter_by(personality=dbpersonality)
        elif personality:
            q = q.join('personality').filter_by(name=personality)
            q = q.reset_joinpoint()
        elif archetype:
            q = q.join('personality').filter_by(archetype=dbarchetype)
            q = q.reset_joinpoint()

        if buildstatus:
            dbbuildstatus = HostLifecycle.get_unique(session, buildstatus,
                                                     compel=True)
            q = q.filter_by(status=dbbuildstatus)

        if osname and osversion and archetype:
            # archetype was already resolved above
            dbos = OperatingSystem.get_unique(session, name=osname,
                                              version=osversion,
                                              archetype=dbarchetype,
                                              compel=True)
            q = q.filter_by(operating_system=dbos)
        elif osname or osversion:
            q = q.join('operating_system')
            if osname:
                q = q.filter_by(name=osname)
            if osversion:
                q = q.filter_by(version=osversion)
            q = q.reset_joinpoint()

        if service:
            dbservice = Service.get_unique(session, service, compel=True)
            if instance:
                dbsi = get_service_instance(session, dbservice, instance)
                q = q.join('services_used')
                q = q.filter_by(service_instance=dbsi)
                q = q.reset_joinpoint()
            else:
                q = q.join('services_used', 'service_instance')
                q = q.filter_by(service=dbservice)
                q = q.reset_joinpoint()
        elif instance:
            q = q.join(['services_used', 'service_instance'])
            q = q.filter_by(name=instance)
            q = q.reset_joinpoint()

        if cluster:
            dbcluster = Cluster.get_unique(session, cluster, compel=True)
            q = q.join('_cluster')
            q = q.filter_by(cluster=dbcluster)
            q = q.reset_joinpoint()
        if guest_on_cluster:
            dbcluster = Cluster.get_unique(session, guest_on_cluster,
                                           compel=True)
            q = q.join([HardwareEntity, Machine, '_cluster'])
            q = q.filter_by(cluster=dbcluster)
            q = q.reset_joinpoint()
        if guest_on_share:
            nas_disk_share = Service.get_unique(session, name='nas_disk_share',
                                                compel=True)
            dbshare = ServiceInstance.get_unique(session, name=guest_on_share,
                                                 service=nas_disk_share,
                                                 compel=True)
            NasAlias = aliased(NasDisk)
            q = q.join([HardwareEntity, Machine, 'disks', (NasAlias, NasAlias.id==Disk.id)])
            q = q.filter_by(service_instance=dbshare)
            q = q.reset_joinpoint()
        if fullinfo:
            return q.all()
        return SimpleSystemList(q.all())
