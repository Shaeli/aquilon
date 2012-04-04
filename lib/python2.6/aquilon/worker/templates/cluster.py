# ex: set expandtab softtabstop=4 shiftwidth=4: -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2009,2010,2011,2012  Contributor
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


import logging

from aquilon.aqdb.model import (Cluster, EsxCluster, ComputeCluster,
                                StorageCluster)
from aquilon.worker.templates.base import Plenary, PlenaryCollection
from aquilon.worker.templates.machine import PlenaryMachineInfo
from aquilon.worker.templates.panutils import pan, StructureTemplate
from aquilon.worker.locks import CompileKey


LOGGER = logging.getLogger(__name__)


class PlenaryCluster(PlenaryCollection):
    """
    A facade for the variety of PlenaryCluster subsidiary files
    """
    def __init__(self, dbcluster, logger=LOGGER):
        PlenaryCollection.__init__(self, logger=LOGGER)
        self.dbobj = dbcluster
        self.plenaries.append(PlenaryClusterObject(dbcluster, logger=logger))
        self.plenaries.append(PlenaryClusterData(dbcluster, logger=logger))
        self.plenaries.append(PlenaryClusterClient(dbcluster, logger=logger))


Plenary.handlers[Cluster] = PlenaryCluster
Plenary.handlers[ComputeCluster] = PlenaryCluster
Plenary.handlers[EsxCluster] = PlenaryCluster
Plenary.handlers[StorageCluster] = PlenaryCluster


class PlenaryClusterData(Plenary):

    template_type = ""

    def __init__(self, dbcluster, logger=LOGGER):
        Plenary.__init__(self, dbcluster, logger=logger)
        self.name = dbcluster.name
        if dbcluster.metacluster:
            self.metacluster = dbcluster.metacluster.name
        else:
            self.metacluster = "global"
        self.plenary_core = "clusterdata"
        self.plenary_template = dbcluster.name

    def get_key(self):
        return CompileKey(domain=self.dbobj.branch.name,
                          profile=self.plenary_template_name, logger=self.logger)

    def body(self, lines):
        lines.append("include { 'pan/units' };")
        lines.append("include { 'pan/functions' };")
        lines.append("")
        lines.append('"/system/cluster/name" = %s;' % pan(self.name))
        lines.append('"/system/cluster/type" = %s;' %
                        pan(self.dbobj.cluster_type))

        dbloc = self.dbobj.location_constraint
        lines.append('"/system/cluster/sysloc/location" = %s;' %
                     pan(dbloc.sysloc()))
        if dbloc.continent:
            lines.append('"/system/cluster/sysloc/continent" = %s;' %
                         pan(dbloc.continent.name))
        if dbloc.city:
            lines.append('"/system/cluster/sysloc/city" = %s;' %
                         pan(dbloc.city.name))
        if dbloc.campus:
            lines.append('"/system/cluster/sysloc/campus" = %s;' %
                         pan(dbloc.campus.name))
            ## maintaining this so templates dont break
            ## during transtion period.. should be DEPRECATED
            lines.append('"/system/cluster/campus" = %s;' %
                         pan(dbloc.campus.name))
        if dbloc.building:
            lines.append('"/system/cluster/sysloc/building" = %s;' %
                         pan(dbloc.building.name))
        if dbloc.rack:
            lines.append('"/system/cluster/rack/row" = %s;' %
                         pan(dbloc.rack.rack_row))
            lines.append('"/system/cluster/rack/column" = %s;' %
                         pan(dbloc.rack.rack_column))
            lines.append('"/system/cluster/rack/name" = %s;' %
                         pan(dbloc.rack.name))

        lines.append('"/system/cluster/down_hosts_threshold" = %d;' %
                     self.dbobj.dht_value)
        dmt_value = self.dbobj.dmt_value
        if (dmt_value is not None):
            lines.append('"/system/cluster/down_maint_threshold" = %d;' %
                         dmt_value)
        if (self.dbobj.down_hosts_percent):
            lines.append('"/system/cluster/down_hosts_percent" = %d;' %
                         self.dbobj.down_hosts_threshold)
            lines.append('"/system/cluster/down_hosts_as_percent" = %s;' %
                         pan(self.dbobj.down_hosts_percent))
        if (self.dbobj.down_maint_percent):
            lines.append('"/system/cluster/down_maint_percent" = %d;' %
                         self.dbobj.down_maint_threshold)
            lines.append('"/system/cluster/down_maint_as_percent" = %s;' %
                         pan(self.dbobj.down_maint_percent))
        lines.append("")
        # Only use system names here to avoid circular dependencies.
        # Other templates that needs to look up the underlying values use:
        # foreach(idx; host; value("/system/cluster/members")) {
        #     v = value("//" + host + "/system/foo/bar/baz");
        # );
        lines.append('"/system/cluster/members" = %s;' %
                     pan(sorted([member.fqdn for member in
                                 self.dbobj.hosts])))

        lines.append("")
        for resource in sorted(self.dbobj.resources):
            lines.append("'/system/resources/%s' = push(%s);" % (
                         resource.resource_type,
                         pan(StructureTemplate(resource.template_base +
                                               '/config'))))
        lines.append('"/system/build" = %s;' % pan(self.dbobj.status.name))
        if self.dbobj.allowed_personalities:
            lines.append('"/system/cluster/allowed_personalities" = %s;' %
                         pan(sorted(["%s/%s" % (p.archetype.name, p.name)
                                     for p in self.dbobj.allowed_personalities])))
        lines.append("")
        lines.append('"/metadata/template/branch/name" = %s;' %
                     pan(self.dbobj.branch.name))
        lines.append('"/metadata/template/branch/type" = %s;' %
                     pan(self.dbobj.branch.branch_type))
        if self.dbobj.branch.branch_type == 'sandbox':
            lines.append('"/metadata/template/branch/author" = %s;' %
                         pan(self.dbobj.sandbox_author.name))

        fname = "body_%s" % self.dbobj.cluster_type
        if hasattr(self, fname):
            getattr(self, fname)(lines)

    def body_esx(self, lines):
        if self.metacluster:
            lines.append('"/system/metacluster/name" = %s;' %
                         pan(self.metacluster))
        lines.append('"/system/cluster/ratio" = %s;' % pan([
                            self.dbobj.vm_count,
                            self.dbobj.host_count]))
        lines.append('"/system/cluster/max_hosts" = %d;' %
                     self.dbobj.max_hosts)
        lines.append('')
        machines = {}
        for machine in sorted(self.dbobj.machines):
            if not machine.interfaces or not machine.disks:
                # Do not bother creating entries for VMs that are incomplete.
                continue
            pmac = PlenaryMachineInfo(machine)
            macdesc = {'hardware': StructureTemplate(pmac.plenary_template_name)}

            # One day we may get to the point where this will be required.
            if (machine.host):
                # we fill this in manually instead of just assigning
                # 'system' = value("hostname:/system")
                # because the target host might not actually have a profile.
                arch = machine.host.archetype
                os = machine.host.operating_system
                pn = machine.primary_name.fqdn
                macdesc["system"] = {'archetype': {'name': arch.name,
                                                   'os': os.name,
                                                   'osversion': os.version},
                                     'network': {'hostname': pn.name,
                                                 'domainname': pn.dns_domain}}

            machines[machine.label] = macdesc
        lines.append('"/system/cluster/machines" = %s;' % pan(machines))


class PlenaryClusterObject(Plenary):
    """
    A cluster has its own output profile, so the plenary cluster template
    is an object template that includes the data about which machines
    are contained inside the cluster (via an include of the clusterdata plenary)
    """

    template_type = "object"

    def __init__(self, dbcluster, logger=LOGGER):
        Plenary.__init__(self, dbcluster, logger=logger)
        self.name = dbcluster.name
        if dbcluster.metacluster:
            self.metacluster = dbcluster.metacluster.name
        else:
            self.metacluster = "global"
        self.loadpath = dbcluster.personality.archetype.name
        self.plenary_core = "clusters"
        self.plenary_template = dbcluster.name

    def get_key(self):
        return CompileKey(domain=self.dbobj.branch.name,
                          profile=self.plenary_template_name, logger=self.logger)

    def body(self, lines):
        lines.append("include { 'pan/units' };")
        lines.append("include { 'pan/functions' };")
        lines.append("include { 'clusterdata/%s' };" % self.name)
        lines.append("include { 'archetype/base' };")

        for servinst in sorted(self.dbobj.service_bindings):
            lines.append("include { 'service/%s/%s/client/config' };" % \
                         (servinst.service.name, servinst.name))

        lines.append("include { 'personality/%s/config' };" %
                     self.dbobj.personality.name)
        lines.append("include { 'archetype/final' };")



class PlenaryClusterClient(Plenary):
    """
    A host that is a member of a cluster will include the cluster client
    plenary template. This just names the cluster and nothing more.
    """

    template_type = ""

    def __init__(self, dbcluster, logger=LOGGER):
        Plenary.__init__(self, dbcluster, logger=logger)
        self.name = dbcluster.name
        self.plenary_core = "cluster/%s" % self.name
        self.plenary_template = "client"

    def get_key(self):
        # This takes a domain lock because it could affect all clients...
        return CompileKey(domain=self.dbobj.branch.name, logger=self.logger)

    def body(self, lines):
        lines.append('"/system/cluster/name" = %s;' % pan(self.name))
        # we could just use a PAN external reference to pull in this
        # value from the cluster template, i.e. using
        #  value('clusters/'+value('/system/cluster/name')+':/system/resources')
        # but since we know that these templates are always in sync,
        # we can duplicate the content here to avoid the possibility of
        # circular external references.
        for resource in sorted(self.dbobj.resources):
            lines.append("'/system/cluster/resources/%s' = push(%s);" % (
                         resource.resource_type,
                         pan(StructureTemplate(resource.template_base +
                                               '/config'))))
        lines.append("include { if_exists('features/' + value('/system/archetype/name') + '/%s/%s/config') };"
                     % (self.dbobj.personality.archetype.name,
                        self.dbobj.personality.name))
