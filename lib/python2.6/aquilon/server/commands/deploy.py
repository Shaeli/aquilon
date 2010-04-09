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
"""Contains the logic for `aq deploy`."""


import os

from aquilon.server.broker import BrokerCommand
from aquilon.exceptions_ import ProcessException, ArgumentError
from aquilon.server.dbwrappers.domain import verify_domain
from aquilon.server.processes import run_command


class CommandDeploy(BrokerCommand):

    required_parameters = ["domain"]
    requires_readonly = True

    def render(self, session, logger, domain, to, **arguments):
        """ This currently ignores the 'to' parameter."""

        # Verify that it exists before trying to deploy it.
        dbdomain = verify_domain(session, domain,
                self.config.get("broker", "servername"))
        domaindir = os.path.join(self.config.get("broker", "templatesdir"),
                dbdomain.name)
        git_env={"PATH":"%s:%s" % (self.config.get("broker", "git_path"),
                os.environ.get("PATH", ""))}
        try:
            run_command(["git", "pull", domaindir], env=git_env, logger=logger,
                        path=self.config.get("broker", "kingdir"))
        except ProcessException, e:
            run_command(["git", "reset", "--hard"], env=git_env, logger=logger,
                        path=self.config.get("broker", "kingdir"))
            raise ArgumentError("\n%s%s" %(e.out,e.err))
        return

