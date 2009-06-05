#!/usr/bin/env python2.5
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
""" For dsdb/sybase specific functionality and access"""

import os
import sys
import ms.version
from copy import copy

ms.version.addpkg('sybase', '0.39-15.0.0.17')
import Sybase

from dispatch_table import dispatch_tbl as dt

class DsdbConnection(object):
    """ Wraps connections to DSDB """
    def __init__(self, fake=False, *args, **kw):

#10/23/08 Heavy turonover blackout: at present it's impossible
#         to put this in aurora/dsdb/4.4.3 as we'd like to.

#TODO: failover support
        self.region = (os.environ.get('SYS_REGION') or None)
        if self.region == 'eu':
            self.dsn = 'LNP_DSDB11'
        elif self.region == 'hk':
            self.dsn = 'HKP_DSDB11'
        elif self.region == 'tk':
            self.dsn = 'TKP_DSDB11'
        else:
            self.dsn = 'NYP_DSDB11'
        assert self.dsn

        #FIXME: same as above: T/O restrictions
        krbusrs = 'daqscott, samsh'
        krbusrs = krbusrs.split(',')
        assert krbusrs

        self.fake = fake

        self.syb = None
        if os.environ.get('USER') in krbusrs:
            self.dsn = 'NYP_DSDB11'
            self._get_krb_cnxn()

        if not self.syb or not self.syb._is_connected:
            #TODO: pull password from afs
            self.syb = Sybase.connect(self.dsn, 'dsdb_guest', 'dsdb_guest',
                                  'dsdb', auto_commit='0')
        assert self.syb._is_connected

        ###Impostor attrs only used in unit tests for data refresh
        if self.fake:
            self._fake_data = {}
            #self.fake_types = self.cfg.get('DEFAULT','fake_types')
            #TODO: cfg file in DSDB (T/O restrictions)
            self.fake_types = 'country, campus, city, building, network'
            assert self.fake_types

    def run_query(self,sql):
        """Runs query sql. Note use runSybaseProc to call a stored procedure.
            Parameters:
                sql - SQL to run
            Returns:
                Sybase cursor object"""
        rs = self.syb.cursor()
        try:
           rs.execute(sql)
           return rs
        except Sybase.DatabaseError, e:
            print e

    def run_proc(self, proc, parameters):
        """Runs procedure with supplied parameters.
            Parameters:
                proc - Proc to call
                paramaters - List of parameters to the stored proc.
            Returns:
                Sybase cursor object"""
        rs = self.syb.cursor()
        try:              #not so sure we need all the fancyness
            rs.callproc(proc, parameters)
            return rs
        except Sybase.DatabaseError, e:
            print e

    #TODO: check for kw 'bldgs' as type list for networks by bldg
    #TODO: rename oper (operator? not quite. more like data_type)
    def dump(self, data_type, *args, **kw):
        """ wraps the real 'dump' method for testing.

            add 'fake' to args, and method = 'removed', 'added', 'updated'
            example:
                db.dump('country','fake', method='removed') """

        if data_type not in dt.keys():
            raise KeyError('%s is not a valid dump operation'% data_type)

        if self.fake:
            if data_type not in self.fake_types:
                raise ValueError('%s not available for impostor use'% data_type)
            else:
                #cache the data between tests
                if data_type not in self._fake_data.keys():
                    self._fake_data[data_type] = FakeData(data_type,
                                                          self._dump(data_type))

            return getattr(self._fake_data[data_type], kw['method'])
        elif data_type == 'buildings_by_campus':
            if kw.has_key('campus'):
                campus = kw.pop('campus')
            else:
                msg = "Campus is a required Argument for 'buildings_by_campus'"
            sql = dt[data_type]
            sql += "'%s'"%(campus)
            return self.run_query(sql).fetchall()

        else:
            #do the regular dump routine
            return self.run_query(dt[data_type]).fetchall()
            #this is sorta useless at the moment...
            return self._dump(dt[data_type])

    def _dump(self, data_type, *args, **kw):
        try:
            return self.run_query(dt[data_type]).fetchall()
        except Exception,e:
            print e

    def _get_principal(self):
        for line in open('/ms/dist/syb/dba/files/sgp.dat').xreadlines():
            svr, principal = line.split()
            if svr == self.dsn:
                return principal

        raise ValueError('no principal found for %s'%(self.dsn))

    def _get_krb_cnxn(self):
        #regional copies don't accept kerberos login
        self.dsn = 'NYP_DSDB11'
        principal = self._get_principal()

        self.syb = Sybase.connect(self.dsn, '', '', 'dsdb',
                                      delay_connect=1)

        self.syb.set_property(Sybase.CS_SEC_NETWORKAUTH, Sybase.CS_TRUE)
        self.syb.set_property(Sybase.CS_SEC_SERVERPRINCIPAL,
                              self._get_principal())
        try:
            self.syb.connect()
        except Sybase.DatabaseError, e:
            #swallow the error and fail back to non-kerberized
            pass

    def get_network_by_sysloc(self,loc):
        """ append a sysloc to the base query, get networks"""
        #TODO: make it general case somehow
        s = "    AND location = '%s' \n    ORDER BY A.net_ip_addr"%(loc)
        sql = '\n'.join([dt['net_base'], s])

        data = self.run_query(sql)
        if data is not None:
            return data.fetchall()
        else:
            return None

    def get_host_pod(self,host):
        sql    = """
        SELECT boot_path FROM network_host A, bootparam B
        WHERE A.host_name   =  \'%s\'
          AND A.machine_id  =  B.machine_id
          AND B.boot_key    =  \'podname\'
          AND B.state       >= 0"""%(host)

        return self.run_query(sql).fetchall()[0][0]

    def close(self):
        self.syb.close()

class FakeData(object):
    """ holds a set of data and a few handy manipulations for testing
        pretend the 'real' data set is the current set - its last item """

    def __init__(self, datatype, data, *args, **kw):
        if type(data) != list:
            raise ValueError('data must be a list')

        #deep copy the data list as we'll be modifying it
        self._last = data.pop()
        self.removed = copy(data)

        self._modified_info  = 'AQUILON '+self._last[1]
        self._upd = (self._last[0], self._modified_info, self._last[2])

        self.added = copy(data)
        self.added.append(self._upd)

        self.updated = copy(data)
        self.updated.append(self._last)

if __name__ == '__main__':
    from pprint import pprint

    db = DsdbConnection()
    assert db

    print db.get_network_by_sysloc('np.ny.na')

    ops = ('net_type','campus','campus_entries','country','city','building',
           'np_network')  #omitting 'bucket','network_full','net_ids'

    #for i in ops:
    #    print 'Dump(%s) from dsdb:\n%s\n'%(i, db.dump(i))

    host = 'blackcomb'
    print "getting host data for '%s'"%(host)
    print 'host %s is in the "%s" pod'%(host,db.get_host_pod(host))

    print 'buildings in ny campus:'
    pprint(db.dump('buildings_by_campus', campus='ny'), indent =4)
    print ' '

    #del(db) #BORG anyway dude...

    #db = DsdbConnection(fake=True)
    #for m in ('removed', 'added', 'updated'):
    #    pprint(db.dump('country', method=m), indent=4)
    #    print

    db.close()
