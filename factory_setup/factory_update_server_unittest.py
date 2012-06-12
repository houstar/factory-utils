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


BASE_DIR = os.path.dirname(os.path.realpath(__file__))


class BasicTests(unittest.TestCase):
  def testMd5sumCalculation(self):
    md5sum = factory_update_server.CalculateMd5sum(
        os.path.join(BASE_DIR, 'testdata/shopfloor/autotest.tar.bz2'))
    self.assertEqual(md5sum, '36a7e683170c4bf06982746a2de9cbee')


class FactoryUpdateServerTest(unittest.TestCase):
  def setUp(self):
    self.work_dir = tempfile.mkdtemp(prefix='dts')
    self._CreateUpdateServer()

  def _CreateUpdateServer(self):
    self.update_server = factory_update_server.FactoryUpdateServer(
        self.work_dir, poll_interval_sec=0.1)

  def tearDown(self):
    self.update_server.Stop()
    self.assertEqual(0, self.update_server._errors)
    shutil.rmtree(self.work_dir)

  def testThread(self):
    # Start the thread (make sure it starts/stops properly).
    self.update_server.Start()
    self.update_server.Stop()
    self.assertTrue(self.update_server._run_count)

  def testLogic(self):
    self.update_server.RunOnce()

    self.assertTrue(os.path.isdir(os.path.join(self.work_dir, 'autotest')))
    self.assertTrue(self.update_server._rsyncd.poll() is None)

    # No latest.md5sum file at the beginning.
    md5file = os.path.join(self.work_dir, 'autotest/latest.md5sum')
    self.assertFalse(os.path.exists(md5file))
    self.assertEqual(0, self.update_server._update_count)

    tarball_src = os.path.join(BASE_DIR, 'testdata/shopfloor/autotest.tar.bz2')
    tarball_dest = os.path.join(self.work_dir, 'autotest.tar.bz2')

    # Put partially-written autotest.tar.bz2 into the working folder.
    with open(tarball_dest, "w") as f:
      print >>f, "Not really a bzip2"
    self.update_server.RunOnce()

    # Put autotest.tar.bz2 into the working folder.
    shutil.copy(tarball_src, tarball_dest)
    # Kick the update server
    self.update_server.RunOnce()

    # Check that latest.md5sum is created with correct value and update files
    # extracted.
    self.assertTrue(os.path.isfile(md5file), md5file)
    with open(md5file, 'r') as f:
      self.assertEqual('36a7e683170c4bf06982746a2de9cbee', f.read().strip())
    self.assertTrue(os.path.isdir(os.path.join(
        self.work_dir, 'autotest/36a7e683170c4bf06982746a2de9cbee')))
    self.assertEqual(1, self.update_server._update_count)

    # Kick the update server again.  Nothing should happen.
    self.update_server.RunOnce()
    self.assertEqual(1, self.update_server._update_count)

    # Stop the update server and set up a new one.  The md5sum file
    # should be recreated.
    self.update_server.Stop()
    del self.update_server
    os.unlink(md5file)
    self._CreateUpdateServer()
    self.update_server.RunOnce()
    with open(md5file, 'r') as f:
      self.assertEqual('36a7e683170c4bf06982746a2de9cbee', f.read().strip())

if __name__ == '__main__':
  unittest.main()
