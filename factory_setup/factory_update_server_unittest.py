# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

'''Tests for Factory Update Server.'''

import factory_update_server
import os
import shutil
import sys
import tempfile
import time
import unittest


class FactoryUpdateServerTest(unittest.TestCase):

  def setUp(self):
    self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    self.work_dir = tempfile.mkdtemp(prefix='dts')
    self.update_server = factory_update_server.FactoryUpdateServer(
        self.work_dir)
    self.update_server.start()

  def tearDown(self):
    self.update_server.stop()
    shutil.rmtree(self.work_dir)

  def testUpdateDirCreated(self):
    self.assertTrue(os.path.isdir(os.path.join(self.work_dir, 'autotest')))

  def testRsyncServerStarted(self):
    self.assertTrue(self.update_server._rsyncd.poll() is None)

  def testMd5sumCalculation(self):
    md5sum = factory_update_server.CalculateMd5sum(
        os.path.join(self.base_dir, 'testdata/shopfloor/autotest.tar.bz2'))
    self.assertEqual(md5sum, '36a7e683170c4bf06982746a2de9cbee')

  def testUpdateFilesSetup(self):
    # No latest.md5sum file at the beginning.
    md5file = os.path.join(self.work_dir, 'autotest/latest.md5sum')
    self.assertFalse(os.path.exists(md5file))

    # Put autotest.tar.bz2 into the working folder.
    tarball = os.path.join(self.base_dir, 'testdata/shopfloor/autotest.tar.bz2')
    shutil.copy(tarball, self.work_dir)
    # Wait a little while for update files setup.
    time.sleep(1)

    # Check that latest.md5sum is created with correct value and update files
    # extracted.
    self.assertTrue(os.path.isfile(md5file))
    with open(md5file, 'r') as f:
      md5sum = f.readline().strip()
    self.assertEqual(md5sum, '36a7e683170c4bf06982746a2de9cbee')
    self.assertTrue(os.path.isdir(os.path.join(
        self.work_dir, 'autotest/36a7e683170c4bf06982746a2de9cbee')))


if __name__ == '__main__':
  unittest.main()
