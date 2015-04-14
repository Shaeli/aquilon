#!/usr/bin/env python
# -*- cpy-indent-level: 4; indent-tabs-mode: nil -*-
# ex: set expandtab softtabstop=4 shiftwidth=4:
#
# Copyright (C) 2011,2012,2013,2014,2015  Contributor
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
"""Module for testing the add resourcegroup command."""

if __name__ == "__main__":
    import utils
    utils.import_depends()

import unittest2 as unittest
from brokertest import TestBrokerCommand


class TestAddResourceGroup(TestBrokerCommand):

    def test_100_add_rg_to_cluster(self):
        command = ["add_resourcegroup", "--resourcegroup=utvcs1as1",
                   "--cluster=utvcs1"]
        self.successtest(command)

    def test_110_show_resourcegroup(self):
        command = ["show_resourcegroup", "--cluster=utvcs1"]
        out = self.commandtest(command)
        self.matchoutput(out, "Resource Group: utvcs1as1", command)
        self.matchoutput(out,
                         "Bound to: High Availability Cluster utvcs1",
                         command)

    def test_110_show_all(self):
        command = ["show_resourcegroup", "--all"]
        out = self.commandtest(command)
        self.matchoutput(out, "Resource Group: utvcs1as1", command)

    def test_120_add_fs_to_rg(self):
        command = ["add_filesystem", "--filesystem=fs1", "--type=ext3",
                   "--mountpoint=/mnt", "--blockdevice=/dev/foo/bar",
                   "--bootmount",
                   "--dumpfreq=1", "--fsckpass=3", "--options=ro",
                   "--comments=Some resourcegroup comments",
                   "--resourcegroup=utvcs1as1", "--cluster=utvcs1"]
        self.successtest(command)

    def test_130_show_filesystem(self):
        command = ["show_filesystem", "--filesystem=fs1"]
        out = self.commandtest(command)
        self.matchoutput(out, "Filesystem: fs1", command)
        self.matchoutput(out, "Bound to: Resource Group utvcs1as1", command)
        self.matchoutput(out, "Block Device: /dev/foo/bar", command)
        self.matchoutput(out, "Mount at boot: True", command)
        self.matchoutput(out, "Mountopts: ro", command)
        self.matchoutput(out, "Mountpoint: /mnt", command)
        self.matchoutput(out, "Dump Freq: 1", command)
        self.matchoutput(out, "Fsck Pass: 3", command)
        self.matchoutput(out, "Comments: Some resourcegroup comments", command)

    def test_130_show_resourcegroup(self):
        command = ["show", "resourcegroup", "--resourcegroup", "utvcs1as1"]
        out = self.commandtest(command)
        self.matchoutput(out, "Filesystem: fs1", command)

    def test_130_cat_cluster(self):
        command = ["cat", "--cluster", "utvcs1", "--data"]
        out = self.commandtest(command)
        self.matchoutput(out,
                         '"system/resources/resourcegroup" = '
                         'append(create("resource/cluster/utvcs1/resourcegroup/utvcs1as1/config"));',
                         command)

    def test_130_cat_resourcegroup(self):
        command = ["cat", "--resourcegroup", "utvcs1as1", "--cluster", "utvcs1"]
        out = self.commandtest(command)
        self.matchoutput(out,
                         '"resources/filesystem" = '
                         'append(create("resource/cluster/utvcs1/resourcegroup/utvcs1as1/filesystem/fs1/config"));',
                         command)

    def test_130_cat_resourcegroup_generate(self):
        command = ["cat", "--resourcegroup", "utvcs1as1", "--cluster", "utvcs1",
                   "--generate"]
        out = self.commandtest(command)
        self.matchoutput(out,
                         '"resources/filesystem" = '
                         'append(create("resource/cluster/utvcs1/resourcegroup/utvcs1as1/filesystem/fs1/config"));',
                         command)

    def test_130_cat_filesystem(self):
        command = ["cat", "--cluster", "utvcs1", "--resourcegroup", "utvcs1as1",
                   "--filesystem", "fs1"]
        out = self.commandtest(command)
        self.matchoutput(out,
                         "structure template resource/cluster/utvcs1/resourcegroup/utvcs1as1/filesystem/fs1/config;",
                         command)
        self.matchoutput(out, '"block_device_path" = "/dev/foo/bar";', command)

    def test_130_show_cluster(self):
        command = ["show", "cluster", "--cluster", "utvcs1"]
        out = self.commandtest(command)
        self.matchoutput(out, "    Resource Group: utvcs1", command)
        self.matchoutput(out, "      Filesystem: fs1", command)

    def test_130_show_cluster_proto(self):
        command = ["show", "cluster", "--cluster", "utvcs1", "--format", "proto"]
        cluster = self.protobuftest(command, expect=1)[0]
        rg_msg = None
        for resource in cluster.resources:
            if resource.name == "utvcs1as1" and \
               resource.type == "resourcegroup":
                rg_msg = resource
        self.assertTrue(rg_msg,
                        "Resourcegroup utvcs1as1 not found in the resources. "
                        "Existing resources: %s" %
                        ", ".join(["%s %s" % (res.type, res.name)
                                   for res in cluster.resources]))
        fs_found = False
        for resource in rg_msg.resourcegroup.resources:
            if resource.name == "fs1" and resource.type == "filesystem":
                fs_found = True
                self.assertEqual(resource.fsdata.fstype, "ext3")
                self.assertEqual(resource.fsdata.mountpoint, "/mnt")
                self.assertEqual(resource.fsdata.mount, True)
                self.assertEqual(resource.fsdata.blockdevice, "/dev/foo/bar")
                self.assertEqual(resource.fsdata.opts, "ro")
                self.assertEqual(resource.fsdata.freq, 1)
                self.assertEqual(resource.fsdata.passno, 3)
        self.assertTrue(fs_found,
                        "Filesystem fs1 not found in the resourcegroup. "
                        "Existing resources: %s" %
                        ", ".join(["%s %s" % (res.type, res.name)
                                   for res in rg_msg.resourcegroup.resources]))

    def test_140_add_empty(self):
        # Add an empty resourcegroup, that won't have any resources in it
        command = ["add_resourcegroup", "--resourcegroup", "empty",
                   "--cluster", "utvcs1"]
        self.successtest(command)

    def test_141_del_empty(self):
        # Test deleting a resourcegroup that never had any resources, so the
        # BundleResource object is never created
        command = ["del_resourcegroup", "--resourcegroup", "empty",
                   "--cluster", "utvcs1"]
        self.successtest(command)

    def test_200_add_bad_type(self):
        command = ["add_resourcegroup", "--resourcegroup=utvcs1as1",
                   "--cluster=utvcs1", "--required_type=non-existent-type"]
        err = self.badrequesttest(command)
        self.matchoutput(err, "Unknown resource type 'non-existent-type'.",
                         command)

    def test_200_stacked_resourcegroup(self):
        command = ["add_resourcegroup", "--resourcegroup=utvcs1as1",
                   "--cluster=utvcs1", "--required_type=resourcegroup"]
        err = self.badrequesttest(command)
        self.matchoutput(err, "Bad Request: A resourcegroup can't hold other "
                         "resourcegroups.", command)

    def test_300_del_resourcegroup(self):
        # Check that the plenaries of contained resources get cleaned up
        rg_base = ["resource", "cluster", "utvcs1", "resourcegroup",
                   "utvcs1as1"]

        rg_path = rg_base[:]
        rg_path.append("config")

        fs_path = rg_base[:]
        fs_path.extend(["filesystem", "fs1", "config"])

        # Verify that we got the paths right
        self.check_plenary_exists(*fs_path)
        self.check_plenary_exists(*rg_path)

        command = ["del_resourcegroup", "--resourcegroup=utvcs1as1",
                   "--cluster=utvcs1"]
        self.successtest(command)

        # The resource plenaries should be gone, and the directory too
        self.check_plenary_gone(*fs_path, directory_gone=True)
        self.check_plenary_gone(*rg_path, directory_gone=True)

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAddResourceGroup)
    unittest.TextTestRunner(verbosity=2).run(suite)
