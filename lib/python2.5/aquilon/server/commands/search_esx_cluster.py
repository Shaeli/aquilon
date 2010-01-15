# ex: set expandtab softtabstop=4 shiftwidth=4: -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2010  Contributor
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
"""Contains the logic for `aq search esx cluster`."""


from sqlalchemy.orm import aliased

from aquilon.exceptions_ import ArgumentError
from aquilon.server.broker import BrokerCommand
from aquilon.server.formats.cluster import SimpleClusterList
from aquilon.aqdb.model import (EsxCluster, MetaCluster, Archetype,
                                Personality, Domain, Machine,
                                Service, ServiceInstance, NasDisk, Disk)
from aquilon.server.dbwrappers.host import hostname_to_host
from aquilon.server.dbwrappers.location import get_location


class CommandSearchESXCluster(BrokerCommand):

    required_parameters = []

    def render(self, session, cluster, metacluster,
               esx_hostname, virtual_machine, guest,
               domain, archetype, personality, service, instance, share,
               fullinfo, **arguments):
        q = session.query(EsxCluster)
        if cluster:
            dbcluster = EsxCluster.get_unique(session, cluster, compel=True)
            q = q.filter_by(id=dbcluster.id)
        if metacluster:
            dbmetacluster = MetaCluster.get_unique(session, metacluster,
                                                   compel=True)
            q = q.join(['_metacluster'])
            q = q.filter_by(metacluster=dbmetacluster)
            q = q.reset_joinpoint()
        if esx_hostname:
            dbvmhost = hostname_to_host(session, esx_hostname)
            q = q.join('_hosts')
            q = q.filter_by(host=dbvmhost)
            q = q.reset_joinpoint()
        if virtual_machine:
            dbvm = Machine.get_unique(session, virtual_machine, compel=True)
            q = q.join('_machines')
            q = q.filter_by(machine=dbvm)
            q = q.reset_joinpoint()
        if guest:
            dbguest = hostname_to_host(session, guest)
            q = q.join(['_machines', 'machine'])
            q = q.filter_by(host=dbguest)
            q = q.reset_joinpoint()
        if domain:
            dbdomain = Domain.get_unique(session, domain, compel=True)
            q = q.filter_by(domain=dbdomain)

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

        if service:
            dbservice = Service.get_unique(session, name=service, compel=True)
            if instance:
                dbsi = ServiceInstance.get_unique(session, name=instance,
                                                  service=dbservice,
                                                  compel=True)
                q = q.join('_cluster_svc_binding')
                q = q.filter_by(service_instance=dbsi)
                q = q.reset_joinpoint()
            else:
                q = q.join('_cluster_svc_binding', 'service_instance')
                q = q.filter_by(service=dbservice)
                q = q.reset_joinpoint()
        elif instance:
            q = q.join(['_cluster_svc_binding', 'service_instance'])
            q = q.filter_by(name=instance)
            q = q.reset_joinpoint()

        if share:
            nas_disk_share = Service.get_unique(session, name='nas_disk_share',
                                                compel=True)
            dbshare = ServiceInstance.get_unique(session, name=share,
                                                 service=nas_disk_share,
                                                 compel=True)
            NasAlias = aliased(NasDisk)
            q = q.join(['_machines', 'machine', 'disks',
                        (NasAlias, NasAlias.id==Disk.id)])
            q = q.filter_by(service_instance=dbshare)
            q = q.reset_joinpoint()

        # Go through the arguments and make special dicts for each
        # specific set of location arguments that are stripped of the
        # given prefix.
        location_args = {'cluster_': {}, 'vmhost_': {}}
        for prefix in location_args.keys():
            for (k, v) in arguments.items():
                if k.startswith(prefix):
                    # arguments['cluster_building'] = 'dd'
                    # becomes
                    # location_args['cluster_']['building'] = 'dd'
                    location_args[prefix][k.replace(prefix, '')] = v

        dblocation = get_location(session, **location_args['cluster_'])
        if dblocation:
            q = q.filter_by(location_constraint=dblocation)
        dblocation = get_location(session, **location_args['vmhost_'])
        if dblocation:
            q = q.join('_hosts', 'host', 'machine')
            q = q.filter_by(location=dblocation)
            q = q.reset_joinpoint()

        if fullinfo:
            return q.all()
        return SimpleClusterList(q.all())
