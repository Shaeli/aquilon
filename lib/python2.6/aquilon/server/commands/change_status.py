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
"""Contains the logic for `aq change status`."""


from aquilon.exceptions_ import ArgumentError, IncompleteError
from aquilon.server.broker import BrokerCommand
from aquilon.server.dbwrappers.host import hostname_to_host
from aquilon.server.dbwrappers.status import get_status
from aquilon.server.templates.domain import TemplateDomain
from aquilon.server.templates.host import PlenaryHost
from aquilon.server.locks import lock_queue, CompileKey


class CommandChangeStatus(BrokerCommand):

    required_parameters = ["hostname"]

    def render(self, session, logger, hostname, buildstatus, **arguments):
        dbhost = hostname_to_host(session, hostname)

        if buildstatus:
            dbstatus = get_status(session, buildstatus)
            dbhost.status = dbstatus
            session.add(dbhost)

        if not dbhost.archetype.is_compileable:
            return

        session.flush()

        plenary = PlenaryHost(dbhost, logger=logger)
        # Force a host lock as pan might overwrite the profile...
        key = CompileKey(domain=dbhost.domain.name, profile=dbhost.fqdn,
                         logger=logger)
        try:
            lock_queue.acquire(key)
            plenary.write(locked=True)
            td = TemplateDomain(dbhost.domain, logger=logger)
            out = td.compile(session, only=dbhost.fqdn, locked=True)
        except IncompleteError, e:
            raise ArgumentError("Run aq make for host %s first." % dbhost.fqdn)
        except:
            plenary.restore_stash()
            raise
        finally:
            lock_queue.release(key)
        return