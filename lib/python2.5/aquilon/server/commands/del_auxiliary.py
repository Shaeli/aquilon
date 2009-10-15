# ex: set expandtab softtabstop=4 shiftwidth=4: -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2008,2009  Contributor
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
"""Contains the logic for `aq del auxiliary`."""


import os

from aquilon.exceptions_ import ArgumentError, ProcessException
from aquilon.server.broker import BrokerCommand
from aquilon.server.dbwrappers.system import get_system
from aquilon.server.processes import DSDBRunner
from aquilon.server.commands.del_host import delhost_lock
from aquilon.aqdb.model import Auxiliary


class CommandDelAuxiliary(BrokerCommand):

    required_parameters = ["auxiliary"]

    def render(self, session, logger, auxiliary, user, **arguments):
        logger.client_info("Acquiring lock to attempt to delete %s" % auxiliary)
        delhost_lock.acquire()
        try:
            logger.client_info("Acquired lock, attempting to delete %s" %
                               auxiliary)
            # Check dependencies, translate into user-friendly message
            dbauxiliary = get_system(session, auxiliary)
            if not isinstance(dbauxiliary, Auxiliary):
                raise ArgumentError("%s '%s' is not Auxiliary." % (
                                    dbauxiliary.system_type, dbauxiliary.fqdn))

            # FIXME: Look for System dependencies...

            ip = dbauxiliary.ip
            dbmachine = dbauxiliary.machine
            # FIXME: Check to see if this is handled auto-magically by
            # sqlalchemy.
            for dbinterface in dbauxiliary.interfaces:
                dbinterface.system = None
                session.add(dbinterface)

            session.delete(dbauxiliary)
            session.flush()
    
            try:
                dsdb_runner = DSDBRunner(logger=logger)
                dsdb_runner.delete_host_details(ip)
            except ProcessException, e:
                raise ArgumentError("Could not remove host %s from dsdb: %s" %
                            (auxiliary, e))
        finally:
            logger.client_info("Released lock from attempt to delete %s" %
                               auxiliary)
            delhost_lock.release()

        if dbmachine.host:
            # FIXME: Reconfigure
            pass

        return


