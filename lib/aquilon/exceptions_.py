# -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# ex: set expandtab softtabstop=4 shiftwidth=4:
#
# Copyright (C) 2008,2009,2010,2011,2013,2014,2017,2018  Contributor
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
"""Exceptions to be used by Aquilon"""

# DontWrapMixin is only meaningful inside the broker. Import it conditionally,
# so other components don't need to depend on SQLAlchemy
try:
    from sqlalchemy.exc import DontWrapMixin
except ImportError:
    class DontWrapMixin(object):
        pass


def deprecated(message):
    import warnings
    warnings.warn(message, DeprecationWarning, stacklevel=2)


class AquilonError(Exception):
    '''Generic error class.'''


class ArgumentError(AquilonError, DontWrapMixin):
    """Raised for all those conditions where invalid arguments are
    sent to constructed objects.  This error generally corresponds to
    construction time state errors.

    """


class ProtocolError(AquilonError):
    """Raised when an import of a protocol fails

    """


class ProcessException(AquilonError):
    """Raised when a process being executed fails."""
    def __init__(self, command=None, out=None, err=None,
                 code=None, signalNum=None, filtered=None,
                 timeouted=None):
        self.command = command
        self.out = out
        self.err = err
        self.code = code
        self.signalNum = signalNum
        if command:
            msg = "Command '{}' failed".format(command)
        else:
            msg = "Command failed"
        if timeouted:
            msg = msg + " when reaching timeout of {} sec".format(timeouted)
        elif code:
            msg = msg + " with return code '{}'".format(code)
        elif signalNum:
            msg = msg + " with signal '{}'".format(signalNum)
        if err and err.strip():
            msg = msg + " and stderr:\n{}".format(err)
        elif out and out.strip():
            filter_msg = "filtered " if filtered else ""
            msg = msg + " and {}stdout:\n{}".format(filter_msg, out)
        super(ProcessException, self).__init__(msg)


class RollbackException(AquilonError):
    """If this is being thrown, should attempt to rollback any high-level
    activities being executed."""
    # This isn't fully baked yet... might not be necessary.
    def __init__(self, jobid=None, cause=None, *args, **kwargs):
        self.jobid = jobid
        self.cause = cause
        if not args and cause:
            args = [str(cause)]
        AquilonError.__init__(self, *args, **kwargs)


class AuthorizationException(AquilonError):
    """Raised when a principle is not authorized to perform a given
    action on a resource.

    """


class NotFoundException(AquilonError, DontWrapMixin):
    """Raised when a requested resource cannot be found."""


class UnimplementedError(AquilonError):
    """Raised when a command has not been implemented."""


class IncompleteError(AquilonError):
    """Raised when an incomplete/unusable template would be generated."""


class PartialError(AquilonError):
    """Raised when a batch job has some failures."""

    def __init__(self, success, failed, success_msg=None, failed_msg=None):
        msg = []
        if success_msg:
            msg.append(success_msg)
        else:
            msg.append("The following were successful:")
        msg.extend(success)
        if failed_msg:
            msg.append(failed_msg)
        else:
            msg.append("The following failed:")
        msg.extend(failed)
        AquilonError.__init__(self, "\n".join(msg))


class InternalError(AquilonError):
    """Raised when an algorithm error or internal data corruption is seen.

    These should only be raised from "can't happen" code and are
    preferred over assertion errors.
    """


class TransientError(AquilonError):
    """
    Raised when there's a transient failure, e.g. database is not available.
    """
