# -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# ex: set expandtab softtabstop=4 shiftwidth=4:
#
# Copyright (C) 2010,2011,2012,2013,2014,2015  Contributor
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
"""Contains the logic for `aq add interface address`."""

from aquilon.utils import validate_nlist_key
from aquilon.exceptions_ import ArgumentError, IncompleteError, ProcessException
from aquilon.aqdb.model import HardwareEntity, NetworkEnvironment, Interface
from aquilon.worker.broker import BrokerCommand
from aquilon.worker.dbwrappers.dns import grab_address
from aquilon.worker.dbwrappers.interface import (generate_ip,
                                                 assign_address)
from aquilon.worker.processes import DSDBRunner
from aquilon.worker.templates import Plenary


class CommandAddInterfaceAddress(BrokerCommand):

    required_parameters = ['interface']

    def render(self, session, logger, machine, chassis, network_device, fqdn,
               interface, label, network_environment, map_to_primary, **kwargs):

        if machine:
            hwtype = 'machine'
            hwname = machine
        elif chassis:
            hwtype = 'chassis'
            hwname = chassis
        elif network_device:
            hwtype = 'network_device'
            hwname = network_device

        dbnet_env = NetworkEnvironment.get_unique_or_default(session,
                                                             network_environment)

        dbhw_ent = HardwareEntity.get_unique(session, hwname,
                                             hardware_type=hwtype, compel=True)
        dbinterface = Interface.get_unique(session, hardware_entity=dbhw_ent,
                                           name=interface, compel=True)

        oldinfo = DSDBRunner.snapshot_hw(dbhw_ent)

        audit_results = []
        ip = generate_ip(session, logger, dbinterface,
                         network_environment=dbnet_env,
                         audit_results=audit_results, **kwargs)

        if dbinterface.interface_type == "loopback":
            # Switch loopback interfaces may use e.g. the network address as an
            # IP address
            relaxed = True
        else:
            relaxed = False

        if not fqdn:
            if not dbhw_ent.primary_name:
                raise ArgumentError("{0} has no primary name, can not "
                                    "auto-generate the DNS record.  "
                                    "Please specify --fqdn.".format(dbhw_ent))
            if label:
                name = "%s-%s-%s" % (dbhw_ent.primary_name.fqdn.name, interface,
                                     label)
            else:
                name = "%s-%s" % (dbhw_ent.primary_name.fqdn.name, interface)
            fqdn = "%s.%s" % (name, dbhw_ent.primary_name.fqdn.dns_domain)

        if label is None:
            label = ""
        elif label == "hostname":
            # When add_host sets up Zebra, it always uses the label 'hostname'.
            # Due to the primary IP being special, add_interface_address cannot
            # really emulate what add_host does, so tell the user where to look.
            raise ArgumentError("The 'hostname' label can only be managed "
                                "by add_host/del_host.")

        # The label will be used as an nlist key
        if label:
            validate_nlist_key("label", label)

        # TODO: add allow_multi=True
        dbdns_rec, newly_created = grab_address(session, fqdn, ip, dbnet_env,
                                                relaxed=relaxed)
        ip = dbdns_rec.ip
        dbnetwork = dbdns_rec.network
        delete_old_dsdb_entry = not newly_created and not dbdns_rec.assignments

        # Reverse PTR control. Auxiliary addresses should point to the primary
        # name by default, with some exceptions.
        if (map_to_primary is None and dbhw_ent.primary_name and
                dbinterface.interface_type != "management" and
                dbdns_rec.fqdn.dns_environment == dbhw_ent.primary_name.fqdn.dns_environment):
            map_to_primary = True

        if map_to_primary:
            if not dbhw_ent.primary_name:
                raise ArgumentError("{0} does not have a primary name, cannot "
                                    "set the reverse DNS mapping."
                                    .format(dbhw_ent))
            if (dbhw_ent.primary_name.fqdn.dns_environment !=
                    dbdns_rec.fqdn.dns_environment):
                raise ArgumentError("{0} lives in {1:l}, not {2:l}."
                                    .format(dbhw_ent,
                                            dbhw_ent.primary_name.fqdn.dns_environment,
                                            dbdns_rec.fqdn.dns_environment))
            if dbinterface.interface_type == "management":
                raise ArgumentError("The reverse PTR for management addresses "
                                    "should not point to the primary name.")
            dbdns_rec.reverse_ptr = dbhw_ent.primary_name.fqdn

        # Check that the network ranges assigned to different interfaces
        # do not overlap even if the network environments are different, because
        # that would confuse routing on the host. E.g. if eth0 is an internal
        # and eth1 is an external interface, then using 192.168.1.10/24 on eth0
        # and using 192.168.1.20/26 on eth1 won't work.
        for addr in dbhw_ent.all_addresses():
            if addr.network != dbnetwork and \
               addr.network.network.overlaps(dbnetwork.network):
                raise ArgumentError("{0} in {1:l} used on {2:l} overlaps "
                                    "requested {3:l} in "
                                    "{4:l}.".format(addr.network,
                                                    addr.network.network_environment,
                                                    addr.interface,
                                                    dbnetwork,
                                                    dbnetwork.network_environment))

        assign_address(dbinterface, ip, dbnetwork, label=label, logger=logger)
        session.flush()

        dbhost = getattr(dbhw_ent, "host", None)
        if dbhost:
            plenary_info = Plenary.get_plenary(dbhost, logger=logger)
            with plenary_info.get_key():
                try:
                    try:
                        plenary_info.write(locked=True)
                    except IncompleteError:
                        # FIXME: if this command is used after "add host" but
                        # before "make", then writing out the template will fail
                        # due to required services not being assigned. Ignore
                        # this error for now.
                        plenary_info.restore_stash()

                    dsdb_runner = DSDBRunner(logger=logger)
                    if dbhost.archetype.name == 'aurora':
                        try:
                            dsdb_runner.show_host(dbdns_rec.fqdn.name)
                        except ProcessException as e:
                            raise ArgumentError("Could not find host in DSDB: "
                                                "%s" % e)
                    else:
                        if delete_old_dsdb_entry:
                            dsdb_runner.delete_host_details(dbdns_rec.fqdn, ip)
                        dsdb_runner.update_host(dbhw_ent, oldinfo)
                        dsdb_runner.commit_or_rollback("Could not add host to DSDB")
                except:
                    plenary_info.restore_stash()
                    raise
        else:
            dsdb_runner = DSDBRunner(logger=logger)
            if delete_old_dsdb_entry:
                dsdb_runner.delete_host_details(dbdns_rec.fqdn, ip)
            dsdb_runner.update_host(dbhw_ent, oldinfo)
            dsdb_runner.commit_or_rollback("Could not add host to DSDB")

        for name, value in audit_results:
            self.audit_result(session, name, value, **kwargs)
        return
