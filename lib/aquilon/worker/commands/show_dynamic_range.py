# -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# ex: set expandtab softtabstop=4 shiftwidth=4:
#
# Copyright (C) 2008,2009,2010,2011,2012,2013,2015,2016,2017,2018  Contributor
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
"""Contains the logic for `aq show dynamic range`."""

from ipaddress import ip_address

from aquilon.aqdb.model import DynamicStub, DnsEnvironment
from aquilon.aqdb.model.network import get_net_id_from_ip

from aquilon.exceptions_ import NotFoundException
from aquilon.worker.broker import BrokerCommand
from aquilon.worker.formats.dynamic_range import DynamicRange


class CommandShowDynamicRange(BrokerCommand):
    def render(self, session, fqdn, ip, dns_environment, **_):
        dbdns_env = DnsEnvironment.get_unique_or_default(session,
                                                         dns_environment)

        dbdns_rec = None

        if fqdn:
            dbdns_rec = DynamicStub.get_unique(session, fqdn=fqdn,
                                               dns_environment=dbdns_env,
                                               compel=True)
            dbnetwork = dbdns_rec.network
            ip = dbdns_rec.ip
        if ip:
            dbnetwork = get_net_id_from_ip(session, ip)

        if not dbdns_rec:
            dbdns_rec = session.query(DynamicStub).filter_by(ip=ip, network=dbnetwork).first()

        start = int(ip)
        end = int(ip)
        range_class = None

        if not dbdns_rec:
            raise NotFoundException(
                '{} is not part of a dynamic range'.format(ip))

        range_class = dbdns_rec.range_class

        q = session.query(DynamicStub.ip)
        q = q.filter_by(network=dbnetwork, range_class=range_class)
        all_stubs = frozenset(int(stub.ip) for stub in q)

        while start > int(dbnetwork.network_address) and start - 1 in all_stubs:
            start = start - 1

        while end < int(dbnetwork.broadcast_address) and end + 1 in all_stubs:
            end = end + 1

        return DynamicRange(dbnetwork, ip_address(start), ip_address(end), range_class)
