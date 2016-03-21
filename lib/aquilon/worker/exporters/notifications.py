# -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# ex: set expandtab softtabstop=4 shiftwidth=4:
#
# Copyright (C) 2008,2009,2010,2011,2012,2013,2014,2015,2016  Contributor
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
import os
import sys
from time import time
from uuid import uuid4
from struct import pack

from twisted.python import log
from twisted.internet import reactor
from twisted.internet.protocol import ClientCreator, Protocol
from twisted.internet.endpoints import UNIXClientEndpoint

from aquilon.config import Config
from aquilon.exceptions_ import ProtocolError
from aquilon.worker.exporter import (ExportHandler, ExporterNotification,
                                     register_exporter)

# TODO: This should be merged with formats/formatters.py
class ProtocolBufferMixin(object):
    __loaded_protocols = {}
    def get_protobuf_msgclass(self, module, msgclass):
        if module in self.__loaded_protocols and \
           self.__loaded_protocols[module] is False:  # pragma: no cover
            raise ProtocolError("Protocol %s: previous import attempt was "
                                "unsuccessful" % module)

        if module not in self.__loaded_protocols:
            config = Config()
            protodir = config.get("protocols", "directory")

            # Modifying sys.path here is ugly. We could try playing with
            # find_module()/load_module(), but there are dependencies between
            # the protocols, that could fail if sys.path is not set up and the
            # protocols are loaded in the wrong order.
            if protodir not in sys.path:
                sys.path.append(protodir)

            try:
                self.__loaded_protocols[module] = __import__(module)
            except ImportError as err:  # pragma: no cover
                self.__loaded_protocols[module] = False
                raise ProtocolError("Protocol %s: %s" % (module, err))

        return getattr(self.__loaded_protocols[module], msgclass)


"""
A Pending notification.  This class is used to store a single protobuf
message that should be sent over the notification interface.
"""
class PendingNotificationEvent(ExporterNotification):
    __slots__ = ['_message']

    def __init__(self, message):
        self._message = message

    def serialize(self, **kwargs):
        return self._message.SerializeToString()


"""
Twisted protocol class compatible with Int32StringReceiver.  This the
sendMessage method expects a PendingNotificationEvent which will then
be written to the transport.
"""
class PublishProtocol(Protocol):
    def sendMessage(self, msg):
        data = msg.serialize()
        dlen = pack('!I', len(data))
        self.transport.write(dlen + data)


@register_exporter('Fqdn', 'HardwareEntity', 'Interface', 'Disk')
class NotificationExportHandler(ExportHandler, ProtocolBufferMixin):

    def __init__(self):
        self.config = Config()
        self._creator = ClientCreator(reactor, PublishProtocol)

    def publish(self, notifications, **kwargs):
        sockname = os.path.join(self.config.get("broker", "sockdir"), "events")
        timeout = 1 # TODO: should be configurable
        # The following construts a Deffered that, connect and then send
        # all of the queued notifications.  This will be processed after
        # the request has finished.  Any errors are logged, but ignored.
        d = self._creator.connectUNIX(sockname, timeout) # pid
        d.addCallback(lambda proto: map(proto.sendMessage, notifications))
        d.addErrback(lambda e: log.msg('Notification push failed: %s', e.getErrorMessage()))

    def fill_fqdn(self, msg, obj):
        msg.entity_type = msg.DNS_RECORD
        msg.dns_record.fqdn = str(obj)
        msg.dns_record.environment_name = obj.dns_environment.name
        return True

    def fill_hardware_entity(self, msg, obj):
        msg.entity_type = msg.HARDWARE_ENTITY
        msg.hardware_entity.label = obj.label
        msg.hardware_entity.model_type = str(obj.model.model_type)
        return True

    def fill_interface(self, msg, obj):
        # We consider interfaces to be a subordinate of a hardware entity, so
        # we # defer to the machine formatter.  However, during an interface
        # delete the relation to the hardware entity is cut; in this case
        # the notification will be generated by the hardware entity update.
        if not obj.hardware_entity:
            return False
        return self.fill_hardware_entity(msg, obj.hardware_entity)

    def fill_disk(self, msg, obj):
        if not obj.machine:
            return False
        return self.fill_hardware_entity(msg, obj.machine)

    def new_notification(self, action, obj, kwargs):
        # Find the function used to fill in the protobuf for the type
        # of object we have been passed.  Given we are ultimatly
        # opperating on database objects the tablename is available.
        for cls in obj.__class__.__mro__:
            if hasattr(cls, '__tablename__'):
                fill = getattr(self, 'fill_' + cls.__tablename__, None)
                if fill: break
        if not fill: # pragma: no cover
            raise ProtocolError("No filler for %s" % repr(obj))

        # Get the protocol buffer message class and construct a new message
        cls = self.get_protobuf_msgclass('aqdnotifications_pb2', 'Notification')
        msg = cls()

        # Fill in the uuid and time stamp.  Calculate a timestamp in
        # milliseconds to avoid overlapping timestamps.
        stamp = uuid4()
        msg.uuid = str(stamp)
        msg.time_stamp = int(time() * 1000)

        # Cheat.  The NotificationAction enum values are repesented in the
        # message class, so we use getattr to extract them
        msg.action = getattr(msg, action)

        # If the requestid and/or user were supplied then fill in the
        # details.  Its possible that these were forgotten when calling
        # the exporter.
        if 'requestid' in kwargs:
            msg.correlation_uuid = str(kwargs['requestid'])
        if 'user' in kwargs:
            msg.correlation_user = kwargs['user']

        # Use the object specific class method to fill in the details
        if not fill(msg, obj):
            return None

        # Finally we return a PendingNotificationEvent (subclass
        # of ExporterNotification)
        return PendingNotificationEvent(msg)

    # The following methods are called by the exporter.  In each case we
    # just call new_notification (see above).

    def create(self, obj, **kwargs):
        return self.new_notification('CREATE', obj, kwargs)

    def update(self, obj, **kwargs):
        return self.new_notification('UPDATE', obj, kwargs)

    def delete(self, obj, **kwargs):
        return self.new_notification('DELETE', obj, kwargs)

