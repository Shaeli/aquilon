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
"""Contains the logic for `aq del tor_switch`."""


from aquilon.exceptions_ import ArgumentError
from aquilon.server.broker import BrokerCommand
from aquilon.server.dbwrappers.tor_switch import get_tor_switch
from aquilon.server.processes import DSDBRunner


class CommandDelTorSwitch(BrokerCommand):

    required_parameters = ["tor_switch"]

    def render(self, session, logger, tor_switch, **arguments):
        dbtor_switch = get_tor_switch(session, tor_switch)
        ip = dbtor_switch.ip

        for iface in dbtor_switch.interfaces:
            logger.info("Before deleting tor_switch '%s', "
                        "removing interface '%s' [%s] boot=%s)" %
                        (dbtor_switch.fqdn,
                         iface.name, iface.mac, iface.bootable))
            session.delete(iface)

        for iface in dbtor_switch.tor_switch_hw.interfaces:
            logger.info("Before deleting tor_switch '%s', "
                        "removing hardware interface '%s' [%s] boot=%s)" %
                        (dbtor_switch.fqdn,
                         iface.name, iface.mac, iface.bootable))
            session.delete(iface)

        session.delete(dbtor_switch.tor_switch_hw)
        session.delete(dbtor_switch)

        # Any switch ports hanging off this switch should be deleted with
        # the cascade delete of the switch.

        if ip:
            dsdb_runner = DSDBRunner(logger=logger)
            try:
                dsdb_runner.delete_host_details(ip)
            except ProcessException, e:
                raise ArgumentError("Could not remove tor_switch from dsdb: %s"
                                    % e)
        return
