#!/ms/dist/python/PROJ/core/2.5.0/bin/python
# ex: set expandtab softtabstop=4 shiftwidth=4: -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# $Header$
# $Change$
# $DateTime$
# $Author$
# Copyright (C) 2008 Morgan Stanley
#
# This module is part of Aquilon
"""Module for testing the del cpu command."""

import os
import sys
import unittest

if __name__ == "__main__":
    BINDIR = os.path.dirname(os.path.realpath(sys.argv[0]))
    SRCDIR = os.path.join(BINDIR, "..", "..")
    sys.path.append(os.path.join(SRCDIR, "lib", "python2.5"))

from brokertest import TestBrokerCommand


class TestDelCpu(TestBrokerCommand):

    def testdelutcpu(self):
        command = "del cpu --cpu utcpu --vendor intel --speed 1000"
        self.noouttest(command.split(" "))

    def testverifydelutcpu(self):
        command = "show cpu --cpu utcpu --speed 1000 --vendor intel"
        out = self.commandtest(command.split(" "))
        self.matchclean(out, "Cpu: intel utcpu 1000 MHz", command)

    def testdelutcpu2(self):
        command = "del cpu --cpu utcpu_1500 --vendor intel --speed 1500"
        self.noouttest(command.split(" "))

    def testverifydelutcpu2(self):
        command = "show cpu --cpu utcpu_1500"
        out = self.commandtest(command.split(" "))
        self.matchclean(out, "Cpu: intel utcpu_1500 1500 MHz", command)


if __name__=='__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDelCpu)
    unittest.TextTestRunner(verbosity=2).run(suite)
