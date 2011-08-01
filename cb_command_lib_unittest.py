#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for the cb_command_lib module."""

import logging
import mox
import re
import os
import shutil
import subprocess
import tempfile
import unittest

import cb_command_lib
import cb_constants
import cb_name_lib
import cb_url_lib
import cb_util_lib

from mox import IsA

from cb_constants import BundlingError


def _CleanUp(obj):
  """Common logic to clean up file system state after a test.

  Assuming permission to delete files and directories specified.

  Args:
    obj: an object with member 'clean_dirs', a list
  """
  for dir_to_clean in obj.clean_dirs:
    if os.path.isdir(dir_to_clean):
      shutil.rmtree(dir_to_clean)


# RunCommand tested in <chromeos_root>/chromite/lib/cros_build_lib_unittest.py


class TestCheckEnvironment(mox.MoxTestBase):
  """Unit test related to CheckEnvironment."""

  def setUp(self):
    self.mox = mox.Mox()
    # defaults used by most tests
    self.image = tempfile.NamedTemporaryFile(suffix='ssd.bin')
    self.image_name = self.image.name
    self.firmware_dest = tempfile.mkdtemp()
    self.mount_point = self.firmware_dest
    self.mox.StubOutWithMock(os, 'getcwd')
    self.mox.StubOutWithMock(cb_command_lib, 'RunCommand')
    self.mock_cres = cb_command_lib.CommandResult()
    self.mock_cres.output = 'uudecode present'
    # do not need to clean up empty temporary file
    self.clean_dirs = [self.firmware_dest]

  def tearDown(self):
    _CleanUp(self)

  def testEnvironmentIsGood(self):
    """Verify return value when environment is all good."""
    os.getcwd().AndReturn('/home/$USER/chromiumos/src/scripts')
    cb_command_lib.RunCommand(IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    self.assertTrue(cb_command_lib.CheckEnvironment(self.image_name,
                                                    self.firmware_dest,
                                                    self.mount_point))

  def testNotInScriptsDirectory(self):
    """Verify return value when script not run from <cros_root/src/scripts."""
    os.getcwd().AndReturn('/home/$USER/chromiumos/src/scripts/lib')
    cb_command_lib.RunCommand(IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    self.assertFalse(cb_command_lib.CheckEnvironment(self.image_name,
                                                     self.firmware_dest,
                                                     self.mount_point))

  def testNoUudecode(self):
    """Verify return value when uudecode not present."""
    os.getcwd().AndReturn('/home/$USER/chromiumos/src/scripts')
    self.mock_cres.output = ''
    cb_command_lib.RunCommand(IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    self.assertFalse(cb_command_lib.CheckEnvironment(self.image_name,
                                                     self.firmware_dest,
                                                     self.mount_point))

  def testSsdDoesNotExist(self):
    """Verify return value when given ssd image file not present."""
    self.image_name = ''
    os.getcwd().AndReturn('/home/$USER/chromiumos/src/scripts')
    cb_command_lib.RunCommand(IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    self.assertFalse(cb_command_lib.CheckEnvironment(self.image_name,
                                                     self.firmware_dest,
                                                     self.mount_point))

  def testBadSsdName(self):
    """Verify return value when given ssd image has bad name."""
    self.image = tempfile.NamedTemporaryFile(suffix='recovery.bin')
    os.getcwd().AndReturn('/home/$USER/chromiumos/src/scripts')
    cb_command_lib.RunCommand(IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    self.assertFalse(cb_command_lib.CheckEnvironment(self.image_name,
                                                     self.firmware_dest,
                                                     self.mount_point))

  def testFirmwareDestinationDoesNotExist(self):
    """Verify return value when environment is all good."""
    self.firmware_dest = ''
    os.getcwd().AndReturn('/home/$USER/chromiumos/src/scripts')
    cb_command_lib.RunCommand(IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    self.assertFalse(cb_command_lib.CheckEnvironment(self.image_name,
                                                     self.firmware_dest,
                                                     self.mount_point))

  def testFirmwareDestinationNotWritable(self):
    """Verify return value when firmware destination directory not writable."""
    self.mox.StubOutWithMock(os, 'access')
    os.getcwd().AndReturn('/home/$USER/chromiumos/src/scripts')
    cb_command_lib.RunCommand(IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    os.access(self.firmware_dest, os.W_OK).AndReturn(False)
    self.mox.ReplayAll()
    self.assertFalse(cb_command_lib.CheckEnvironment(self.image_name,
                                                     self.firmware_dest,
                                                     self.mount_point))

  def testNoMountPoint(self):
    """Verify return value when mount point not given or does not exist."""
    self.mount_point = ''
    os.getcwd().AndReturn('/home/$USER/chromiumos/src/scripts')
    cb_command_lib.RunCommand(IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    self.assertFalse(cb_command_lib.CheckEnvironment(self.image_name,
                                                     self.firmware_dest,
                                                     self.mount_point))

  def testMountPointNotEmpty(self):
    """Verify return value when provided mount point is not empty."""
    self.mox.StubOutWithMock(os, 'listdir')
    os.getcwd().AndReturn('/home/$USER/chromiumos/src/scripts')
    cb_command_lib.RunCommand(IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    os.listdir(self.mount_point).AndReturn(['there_is_a_file'])
    self.mox.ReplayAll()
    self.assertFalse(cb_command_lib.CheckEnvironment(self.image_name,
                                                     self.firmware_dest,
                                                     self.mount_point))


if __name__ == "__main__":
  logging.basicConfig(level=logging.CRITICAL)
  unittest.main()
