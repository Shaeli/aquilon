#!/ms/dist/python/PROJ/core/2.5.0/bin/python
# ex: set expandtab softtabstop=4 shiftwidth=4: -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# $Header$
# $Change$
# $DateTime$
# $Author$
# Copyright (C) 2008 Morgan Stanley
#
# This module is part of Aquilon
""" For Systems and related objects """
from datetime import datetime

import sys
import os

DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(DIR, '..'))

from db_factory import Base
from column_types.aqstr import AqStr
from quattor_server import QuattorServer
from auth.user_principal import UserPrincipal, user_principal
from net.dns_domain import DnsDomain, dns_domain

from sqlalchemy import (Table, Integer, DateTime, Sequence, String, select,
                        Column, ForeignKey, UniqueConstraint)

from sqlalchemy.orm import relation, deferred, backref

class Domain(Base):
    """ Domain is to be used as the top most level for path traversal of the SCM
            Represents individual config repositories """
    __tablename__ = 'domain'
    id = Column(Integer, Sequence('domain_seq'), primary_key = True)
    name = Column(AqStr(32))
    server_id = Column(Integer,
                       ForeignKey('quattor_server.id', name = 'domain_qs_fk'),
                       nullable = False)
    compiler = Column(String(255), nullable = False, default =
                      '/ms/dist/elfms/PROJ/panc/7.2.9/bin/panc')
    owner_id = Column(Integer, ForeignKey(
        'user_principal.id', name = 'domain_user_princ_fk'), nullable = False)

    creation_date = deferred(Column( DateTime, default=datetime.now))
    comments      = deferred(Column('comments', String(255), nullable=True))

    server        = relation(QuattorServer, backref = 'domains')
    owner         = relation(UserPrincipal, uselist = False, backref = 'domain')

domain = Domain.__table__
domain.primary_key.name = 'domain_pk'
domain.append_constraint(
    UniqueConstraint('name',name='domain_uk'))

def populate():
    from db_factory import db_factory, Base
    dbf = db_factory()
    Base.metadata.bind = dbf.engine
    Base.metadata.bind.echo = True
    s = dbf.session()

    domain.create(checkfirst = True)
    if dbf.engine.execute(domain.count()).scalar() < 1:
        qs = s.query(QuattorServer).first()
        cdb = s.query(UserPrincipal).filter_by(name = 'cdb').one()
        daqscott = s.query(UserPrincipal).filter_by(name='daqscott').one()

        p = Domain(name = 'production', server = qs, owner = cdb,
                   comments='The master production area')

        q = Domain(name = 'daqscott', server = qs, owner = daqscott)

        s.add(p)
        s.add(q)
        s.commit()
        s.commit()
        d=s.query(Domain).first()
        assert(d)
