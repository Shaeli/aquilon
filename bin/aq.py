#!/usr/bin/env python2.5
# ex: set expandtab softtabstop=4 shiftwidth=4: -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2009  Contributor
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

'''Client for accessing aqd.

It uses knc by default for an authenticated connection, but can also
connect directly.

'''

import sys
import os
import urllib
import re
# Using this for gethostname for now...
import subprocess
import socket
import httplib

BINDIR = os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.append(os.path.join(BINDIR, "..", "lib", "python2.5"))

import aquilon.client.knchttp

from aquilon.client.optparser import OptParser, ParsingError

class RESTResource(object):
    def __init__(self, httpconnection, uri):
        self.httpconnection = httpconnection
        self.uri = uri
    
    def get(self):
        return self._sendRequest('GET')
    def post(self, **kwargs):
        postData = urllib.urlencode(kwargs)
        mimeType = 'application/x-www-form-urlencoded'
        return self._sendRequest('POST', postData, mimeType)

    def put(self, data, mimeType):
        return self._sendRequest('PUT', data, mimeType)

    def delete(self):
        return self._sendRequest('DELETE')

    def _sendRequest(self, method, data = None, mimeType = None):
        headers = {}
        if mimeType:
            headers['Content-Type'] = mimeType
        self.httpconnection.request(method, self.uri, data, headers)

    def getresponse(self):
        return self.httpconnection.getresponse()


class CustomAction(object):
    """Any custom code that needs to be written to run before contacting
    the server can go here for now.

    Each method should expect to add to the commandOptions object, and
    should have a name that matches the corresponding custom tag in the
    xml option parsing file.

    Code here will run before the reactor starts, and can safely block.
    """

    def __init__(self, action):
        m = getattr(self, action, None)
        if not m:
            raise AquilonError("Internal Error: Unknown action '%s' attempted"
                    % action)
        self.run = m

    def create_bundle(self, commandOptions):
        from subprocess import Popen, PIPE
        from re import search
        from tempfile import mkstemp
        from base64 import b64encode

        p = Popen(("git", "fetch"), stderr=2)
        p.wait()  ## wait for return, but it's okay if this fails
        p = Popen(("git", "status"), stdout=PIPE, stderr=2)
        (out, err) = p.communicate()
        # Looks like git status returns with "1" if there is nothing to commit.
        #if p.returncode:
        #    sys.stdout.write(out)
        #    print >>sys.stderr, "Error running git status, returncode %d" \
        #            % p.returncode
        #    sys.exit(1)
        if not search("nothing to commit", out):
            print >>sys.stderr, "Not ready to commit: %s" % out
            sys.exit(1)

        p = Popen(("git", "log", "origin/master..HEAD"), stdout=PIPE, stderr=2)
        (out,err) = p.communicate()

        if out:
            print >>sys.stdout, "\nThe following changes will be included in this push:\n"
            print >>sys.stdout, "------------------------"
            print >>sys.stdout, str(out)
            print >>sys.stdout, "------------------------"
        else:
            print >>sys.stdout, "\nYou haven't made any changes on this branch\n"
            sys.exit(0)
            
        (handle, filename) = mkstemp()
        try:
            rc = Popen(("git", "bundle", "create", filename, "origin/master..HEAD"),
                        stdout=1, stderr=2).wait()
            if rc:
                print >>sys.stderr, \
                        "Error running git bundle create, returncode %d" % rc
                sys.exit(1)
    
            commandOptions["bundle"] = b64encode(file(filename).read())
        finally:
            os.unlink(filename)


def quoteOptions(options):
    return "&".join([ urllib.quote(k) + "=" + urllib.quote(v) for k, v in options.iteritems() ])


if __name__ == "__main__":
    parser = OptParser( os.path.join( BINDIR, '..', 'etc', 'input.xml' ) )
    try:
        (command, transport, commandOptions, globalOptions) = \
                parser.parse(sys.argv[1:])
    except ParsingError, e:
        print >>sys.stderr, '%s: Option parsing error: %s' % (sys.argv[0],
                                                              e.error)
        print >>sys.stderr, '%s: Try --help for usage details.' % (sys.argv[0])
        sys.exit(1)

    if globalOptions.get('debug'):
        log.startLogging(sys.stderr)
        globalOptions['httpinfo'] = True

    # Setting this as a global default.  It might make sense to set
    # the default to the current running user when running out of a
    # shadow, though.
    default_aquser = "cdb"

    # Default for /ms/dist
    if re.match(r"/ms(/.(global|local)/[^/]+)?/dist/", BINDIR):
        default_aqhost = "nyaqd1"
    # Default for /ms/dev
    elif re.match(r"/ms(/.(global|local)/[^/]+)?/dev/", BINDIR):
        default_aqhost = "nyaqd1"
    else:
        default_aqhost = socket.gethostname()

    if globalOptions.get('noauth'):
        default_aqport = "6901"
    else:
        default_aqport = "6900"

    host = globalOptions.get('aqhost') or default_aqhost
    port = globalOptions.get('aqport') or default_aqport
    aquser = globalOptions.get('aquser') or default_aquser

    # Save these in case there are errors...
    globalOptions["aqhost"] = host
    globalOptions["aqport"] = port

    if transport is None:
        print >>sys.stderr, "Unimplemented command ", command
        exit(1)

    # Convert unicode options to strings
    newOptions = {}
    for k, v in commandOptions.iteritems():
        newOptions[str(k)] = str(v)
    commandOptions = newOptions
    # Should maybe have an input.xml flag on which global options
    # to include... for now it's just debug.
    if globalOptions.get("debug", None):
        commandOptions["debug"] = str(globalOptions["debug"])

    # Quote options so that they can be safely included in the URI
    cleanOptions = {}
    for k, v in commandOptions.iteritems():
        cleanOptions[k] = urllib.quote(v)

    # Decent amount of magic here...
    # Even though the server connection might be tunneled through
    # knc, the easiest way to consistently address the server is with
    # a URI.  That's the first half.
    # The relative URI defined by transport.path comes from the xml
    # file used for options definitions.  This is a standard python
    # string formatting, with references to the options that might
    # be given on the command line.
    uri = str('/' + transport.path % cleanOptions)

    # Add the formatting option into the string.  This is only tricky if
    # a query operator has been specified, otherwise it would just be
    # tacking on (for example) .html to the uri.
    # Do not apply any formatting for commands (transport.expect == 'command').
    if globalOptions.has_key('format') and not transport.expect:
        extension = '.' + urllib.quote(globalOptions["format"])

        query_index = uri.find('?')
        if query_index > -1:
            uri = uri[:query_index] + extension + uri[query_index:]
        else:
            uri = uri + extension

    # create HTTP connection object adhering to the command line request
    if globalOptions.get('noauth'):
        conn = httplib.HTTPConnection(host, port)
    else:
        conn = aquilon.client.knchttp.KNCHTTPConnection(host, port, aquser)

    # run custom command if there's one
    if transport.custom:
        action = CustomAction(transport.custom)
        action.run(commandOptions)

    try:
        if transport.method == 'get':
            # Fun hackery here to get optional parameters into the path...
            # First, figure out what was already included in the path,
            # looking for %(var)s.
            c = re.compile(r'(?<!%)%\(([^)]*)\)s')
            exclude = c.findall(transport.path)

            # Now, pull each of these out of the options.  This is not
            # strictly necessary, but simplifies the uri.
            remainder = commandOptions.copy()
            for e in exclude:
                remainder.pop(e, None)

            if remainder:
                # Almost done.  Just need to account for whether the uri
                # already has a query string.
                if uri.find("?") >= 0:
                    uri = uri + '&' + quoteOptions(remainder)
                else:
                    uri = uri + '?' + quoteOptions(remainder)
            res = RESTResource(conn, uri).get()

        elif transport.method == 'put':
            # FIXME: This will need to be more complicated.
            # In some cases, we may even need to call code here.
            putData = urllib.urlencode(commandOptions)
            mimeType = 'application/x-www-form-urlencoded'
            RESTResource(conn, uri).put(putData, mimeType)

        elif transport.method == 'delete':
            # Again, all command line options should be in the URI already.
            RESTResource(conn, uri).delete()

        elif transport.method == 'post':
            RESTResource(conn, uri).post(**commandOptions)

        else:
            print >>sys.stderr, "Unhandled transport method ", transport.method
            sys.exit(1)

        # handle failed requests
        res = conn.getresponse()
        if res.status != httplib.OK:
            print "%s: %s" % (res.status, res.reason)
            sys.exit(res.status / 100)

        # get data otherwise
        pageData = res.read()


    except socket.error, e:
        print >>sys.stderr, "Network connection problem: %s" % repr(e)
        sys.exit(1)

    except httplib.HTTPException, e:
        print >>sys.stderr, "HTTP transport problem: %s" % repr(e)
        print >>sys.stderr, conn.getError()
        sys.exit(1)

    exit_status = 0

    if transport.expect == 'command':
        if globalOptions.get('noexec'):
            sys.stdout.write(pageData)
        else:
            try:
                proc = subprocess.Popen(pageData, shell = True, stdin = sys.stdin,
                                        stdout = sys.stdout, stderr = sys.stderr)
            except OSError, e:
                print >>sys.stderr, e
                sys.exit(1)

            exit_status = proc.wait()

    else:
        #print pageData,
        sys.stdout.write(pageData)

    sys.exit(exit_status)
