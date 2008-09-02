#!/ms/dist/python/PROJ/core/2.5.0/bin/python
# ex: set expandtab softtabstop=4 shiftwidth=4: -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# $Header$
# $Change$
# $DateTime$
# $Author$
# Copyright (C) 2008 Morgan Stanley
#
# This module is part of Aquilon
"""Contains the logic for `aq add service`."""


from aquilon.server.broker import (format_results, add_transaction, az_check,
                                   BrokerCommand)
from aquilon.aqdb.cfg.cfg_path import CfgPath
from aquilon.aqdb.cfg.tld import Tld
from aquilon.exceptions_ import ArgumentError
import re

class CommandAddPersonality(BrokerCommand):

    required_parameters = ["name"]

    @add_transaction
    @az_check
    def render(self, session, name, user, **arguments):
        valid = re.compile('^[a-zA-Z0-9_-]+$')
        if (not valid.match(name)):
            raise ArgumentError("name '%s' is not valid"%name)

        dbtld = session.query(Tld).filter_by(type="personality").first()

        existing = session.query(CfgPath).filter_by(relative_path=name, tld=dbtld).all()
        if (len(existing) != 0):
            raise ArgumentError("personality '%s' already exists"%name)
        
        dbpersona = CfgPath(tld=dbtld, relative_path=name)
        session.save(dbpersona)
        return


#if __name__=='__main__':