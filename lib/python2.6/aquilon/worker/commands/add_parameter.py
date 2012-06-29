# ex: set expandtab softtabstop=4 shiftwidth=4: -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2012  Contributor
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

from aquilon.worker.broker import BrokerCommand
from aquilon.worker.dbwrappers.parameter import (get_parameter_holder,
                                                 set_parameter)
from aquilon.aqdb.model import Personality, Archetype
from aquilon.worker.templates.personality import PlenaryPersonality
from aquilon.worker.locks import CompileKey
from aquilon.exceptions_ import (IncompleteError, PartialError,
                                 ArgumentError)

class CommandAddParameter(BrokerCommand):

    required_parameters = ['path']

    def process_parameter(self, session, param_holder, path, value, comments):

        dbparameter = set_parameter(session, param_holder, path, value,
                                    compel=False, preclude=True)
        if comments:
            dbparameter.comments = comments

        return dbparameter

    def render(self, session, logger, archetype, personality, feature,
               path, value=None, comments=None, **arguments):

        if not personality:
            if not feature:
                raise ArgumentError("Parameters can be added for personality or feature")
            if not archetype:
                raise ArgumentError("Adding parameter on feature binding needs personality or archetype")

        param_holder = get_parameter_holder(session, archetype, personality,
                                            feature, auto_include=True)

        dbparameter = self.process_parameter(session, param_holder, path, value, comments)
        session.add(dbparameter)
        session.flush()

        personalities = []

        if feature:
            q = session.query(Personality)
            if personality:
                q = q.filter_by(name=personality)
            elif archetype:
                dbarchetype = Archetype.get_unique(session, archetype, compel=True)
                q = q.filter_by(archetype=dbarchetype)
            personalities = q.all()
        else:
            personalities.append(param_holder.holder_object)

        if personalities:
            self.write_plenaries(logger, personalities)

    def write_plenaries(self, logger, personalities):
        idx = 0
        successful = []

        cnt = len(personalities)
        try:
            with CompileKey(logger=logger):
                for personality in personalities:
                    idx += 1
                    if idx % 1000 == 0:  # pragma: no cover
                        logger.client_info("Processing personality %d of %d..." %
                                       (idx, cnt))

                    if not personality.archetype.is_compileable:  # pragma: no cover
                        continue

                    plenary_personality = PlenaryPersonality(personality)
                    plenary_personality.write(locked=True)
                    successful.append(plenary_personality)
        except:
            logger.client_info("Restoring plenary templates.")
            for plenary in successful:
                    plenary.restore_stash()
            raise