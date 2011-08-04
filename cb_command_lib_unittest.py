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


def _AssertFirmwareError(obj):
  """Common logic to assert an error will be raised while listing firmware.

  Args:
    obj: an instance of mox.MoxTestBase
  """
  obj.mox.StubOutWithMock(os.path, 'exists')
  obj.mox.StubOutWithMock(cb_command_lib, 'RunCommand')
  os.path.exists(IsA(str)).AndReturn(True)
  cb_command_lib.RunCommand(IsA(list),
                            redirect_stdout=True).AndReturn(obj.mock_cres)
  obj.mox.ReplayAll()
  obj.assertRaises(BundlingError,
                   cb_command_lib.ListFirmware,
                   obj.image_name,
                   obj.cros_fw)


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


class TestUploadToGsd(mox.MoxTestBase):
  """Unit tests related to UploadToGsd."""

  def testFileExists(self):
    """Verify call sequence when file to upload exists."""
    filename = 'fakefilename'
    self.mox.StubOutWithMock(os.path, 'exists')
    self.mox.StubOutWithMock(cb_command_lib, 'RunCommand')
    os.path.exists(IsA(str)).AndReturn(True)
    cb_command_lib.RunCommand(IsA(list))
    self.mox.ReplayAll()
    cb_command_lib.UploadToGsd(filename)

  def testNoFileGiven(self):
    """Verify error raised when no file given to upload."""
    filename = ''
    self.assertRaises(BundlingError, cb_command_lib.UploadToGsd, filename)

  def testFileDoesNotExist(self):
    """Verify error raised when file given to upload does not exist."""
    filename = 'fakefilename'
    self.mox.StubOutWithMock(os.path, 'exists')
    os.path.exists(IsA(str)).AndReturn(False)
    self.mox.ReplayAll()
    self.assertRaises(BundlingError, cb_command_lib.UploadToGsd, filename)


class TestListFirmware(mox.MoxTestBase):
  """Unit tests related to ListFirmware."""

  def setUp(self):
    self.mox = mox.Mox()
    self.image_name = 'ssd_name_here.bin'
    self.cros_fw = 'chromeos-firmwareupdate'
    self.mock_cres = cb_command_lib.CommandResult()

  def testListFirmwareSuccess(self):
    """Verify return value when all goes well."""
    ec_new_name = 'Alex1234'
    bios_new_name = 'AlexABCD'
    fake_output = '\n'.join(['EC image: ' + ec_new_name,
                             'BIOS image: ' + bios_new_name,
                             './' +  cb_constants.EC_NAME,
                             './' + cb_constants.BIOS_NAME])
    self.mock_cres.output = fake_output
    self.mox.StubOutWithMock(os.path, 'exists')
    self.mox.StubOutWithMock(cb_command_lib, 'RunCommand')
    os.path.exists(IsA(str)).AndReturn(True)
    cb_command_lib.RunCommand(IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    expected = (ec_new_name, bios_new_name)
    actual = cb_command_lib.ListFirmware(self.image_name, self.cros_fw)
    self.assertEqual(expected, actual)

  def testCrosFwDoesNotExist(self):
    """Verify error when provided script name is bad."""
    self.cros_fw = ''
    self.assertRaises(BundlingError,
                      cb_command_lib.ListFirmware,
                      self.image_name,
                      self.cros_fw)

  def testCrosFwFails(self):
    """Verify error when provided script fails to output."""
    self.mock_cres.output = ''
    _AssertFirmwareError(self)

  def testEcNotPresent(self):
    """Verify error when EC firmware file not found."""
    self.mock_cres.output = '\n'.join(['test line 1',
                                       './' + cb_constants.BIOS_NAME])
    _AssertFirmwareError(self)

  def testBiosNotPresent(self):
    """Verify error when BIOS firmware file not found."""
    self.mock_cres.output = '\n'.join(['test line 1',
                                       './' + cb_constants.EC_NAME])
    _AssertFirmwareError(self)

  def testRenamingFails(self):
    """Verify graceful behavior when specific naming info not provided."""
    self.mock_cres.output = '\n'.join(['./' +  cb_constants.EC_NAME,
                                       './' + cb_constants.BIOS_NAME])
    self.mox.StubOutWithMock(os.path, 'exists')
    self.mox.StubOutWithMock(cb_command_lib, 'RunCommand')
    os.path.exists(IsA(str)).AndReturn(True)
    cb_command_lib.RunCommand(IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    expected = (cb_constants.EC_NAME, cb_constants.BIOS_NAME)
    actual = cb_command_lib.ListFirmware(self.image_name, self.cros_fw)
    self.assertEqual(expected, actual)


class TestExtractFiles(mox.MoxTestBase):
  """Unit tests related to ExtractFiles."""

  def setUp(self):
    self.mox = mox.Mox()
    self.cros_fw = '/path/to/chromeos-firmwareupdate'
    self.fw_dir = '/tmp/tmp.ABCD'
    self.mock_cres = cb_command_lib.CommandResult()
    self.mox.StubOutWithMock(os.path, 'exists')
    self.mox.StubOutWithMock(cb_command_lib, 'RunCommand')

  def testExtractFilesSuccess(self):
    """Verify return value when all goes well."""
    self.mock_cres.output = 'Files extracted to ' + self.fw_dir
    os.path.exists(self.cros_fw).AndReturn(True)
    cb_command_lib.RunCommand(IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    os.path.exists(self.fw_dir).AndReturn(True)
    self.mox.ReplayAll()
    self.assertEqual(self.fw_dir, cb_command_lib.ExtractFiles(self.cros_fw))

  def testFirmwareExtractionScriptDoesNotExist(self):
    """Verify return value when firmware extraction script does not exist."""
    os.path.exists(self.cros_fw).AndReturn(False)
    self.mox.ReplayAll()
    expected = None
    actual = cb_command_lib.ExtractFiles(self.cros_fw)
    self.assertEqual(expected, actual)

  def testTmpDirectoryNotNamed(self):
    """Verify return value when extractor fails to tell where it extracted.

    This could be due to extraction script failing or changing output format.
    """
    self.fw_dir = ''
    self.mock_cres.output = 'Not listing tmp results directory'
    os.path.exists(self.cros_fw).AndReturn(True)
    cb_command_lib.RunCommand(IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    expected = None
    actual = cb_command_lib.ExtractFiles(self.cros_fw)
    self.assertEqual(expected, actual)

  def testTmpDirectoryDoesNotExist(self):
    """Verify return value when extractor fails."""
    self.mock_cres.output = 'Lying that files were extracted to ' + self.fw_dir
    os.path.exists(self.cros_fw).AndReturn(True)
    cb_command_lib.RunCommand(IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    os.path.exists(self.fw_dir).AndReturn(False)
    self.mox.ReplayAll()
    expected = None
    actual = cb_command_lib.ExtractFiles(self.cros_fw)
    self.assertEqual(expected, actual)


class TestExtractFirmware(mox.MoxTestBase):
  """Unit tests related to ExtractFirmware."""

  def setUp(self):
    self.mox = mox.Mox()
    self.image_name = '/abs/path/to/image_name'
    self.firmware_dest = '/abs/path/to/dir/firmware/should/go'
    self.mount_point = '/mnt/ssd/here'
    self.mox.StubOutWithMock(cb_command_lib, 'CheckEnvironment')
    self.mox.StubOutWithMock(cb_command_lib, 'RunCommand')
    self.mox.StubOutWithMock(os.path, 'exists')
    self.mox.StubOutWithMock(os, 'listdir')
    self.mox.StubOutWithMock(cb_command_lib, 'ListFirmware')
    self.mox.StubOutWithMock(cb_command_lib, 'ExtractFiles')
    self.mox.StubOutWithMock(shutil, 'copy')
    self.mox.StubOutWithMock(cb_util_lib, 'CheckMd5')


  def testExtractFirmwareSuccess(self):
    """Verify behavior of quiet success when all goes well."""
    cb_command_lib.CheckEnvironment(self.image_name,
                                    self.firmware_dest,
                                    self.mount_point).AndReturn(True)
    cb_command_lib.RunCommand(IsA(list))
    os.path.exists(self.mount_point).AndReturn(True)
    os.listdir(self.mount_point).AndReturn(['stuff', 'is', 'here'])
    cb_command_lib.ListFirmware(IsA(str), IsA(str)).AndReturn(('ec_name',
                                                               'bios_name'))
    cb_command_lib.ExtractFiles(IsA(str)).AndReturn('/tmp/firmware_dir')
    shutil.copy(IsA(str), IsA(str))
    shutil.copy(IsA(str), IsA(str))
    shutil.copy(IsA(str), IsA(str))
    cb_command_lib.RunCommand(IsA(list))
    cb_util_lib.CheckMd5(IsA(str), IsA(str)).AndReturn(True)
    self.mox.ReplayAll()
    cb_command_lib.ExtractFirmware(self.image_name,
                                   self.firmware_dest,
                                   self.mount_point)

  def testCheckEnvironmentBad(self):
    """Verify error when environment check fails."""
    cb_command_lib.CheckEnvironment(self.image_name,
                                    self.firmware_dest,
                                    self.mount_point).AndReturn(False)
    self.mox.ReplayAll()
    self.assertRaises(BundlingError,
                      cb_command_lib.ExtractFirmware,
                      self.image_name,
                      self.firmware_dest,
                      self.mount_point)

  def testMountSsdFailsMountPointNotThere(self):
    """Verify error when SSD image is not mounted."""
    cb_command_lib.CheckEnvironment(self.image_name,
                                    self.firmware_dest,
                                    self.mount_point).AndReturn(True)
    cb_command_lib.RunCommand(IsA(list))
    os.path.exists(self.mount_point).AndReturn(False)
    cb_command_lib.RunCommand(IsA(list))
    self.mox.ReplayAll()
    self.assertRaises(BundlingError,
                      cb_command_lib.ExtractFirmware,
                      self.image_name,
                      self.firmware_dest,
                      self.mount_point)

  def testMountSsdFailsMountPointEmpty(self):
    """Verify error when SSD image is not mounted."""
    cb_command_lib.CheckEnvironment(self.image_name,
                                    self.firmware_dest,
                                    self.mount_point).AndReturn(True)
    cb_command_lib.RunCommand(IsA(list))
    os.path.exists(self.mount_point).AndReturn(True)
    os.listdir(self.mount_point).AndReturn([])
    cb_command_lib.RunCommand(IsA(list))
    self.mox.ReplayAll()
    self.assertRaises(BundlingError,
                      cb_command_lib.ExtractFirmware,
                      self.image_name,
                      self.firmware_dest,
                      self.mount_point)

  def testFirmwareExtractionFails(self):
    """Verify error when firmware extraction fails."""
    cb_command_lib.CheckEnvironment(self.image_name,
                                    self.firmware_dest,
                                    self.mount_point).AndReturn(True)
    cb_command_lib.RunCommand(IsA(list))
    os.path.exists(self.mount_point).AndReturn(True)
    os.listdir(self.mount_point).AndReturn(['stuff', 'is', 'here'])
    cb_command_lib.ListFirmware(IsA(str), IsA(str)).AndReturn(('_ignore',
                                                               '_ignore'))
    cb_command_lib.ExtractFiles(IsA(str))
    cb_command_lib.RunCommand(IsA(list))
    self.mox.ReplayAll()
    self.assertRaises(BundlingError,
                      cb_command_lib.ExtractFirmware,
                      self.image_name,
                      self.firmware_dest,
                      self.mount_point)

  def testImageCorrupted(self):
    """Verify error when firmware extraction corrupts SSD image.

    The primary motivator is potentially calling mount_gpt_image.sh improperly.
    """
    cb_command_lib.CheckEnvironment(self.image_name,
                                    self.firmware_dest,
                                    self.mount_point).AndReturn(True)
    cb_command_lib.RunCommand(IsA(list))
    os.path.exists(self.mount_point).AndReturn(True)
    os.listdir(self.mount_point).AndReturn(['stuff', 'is', 'here'])
    cb_command_lib.ListFirmware(IsA(str), IsA(str)).AndReturn(('_ignore',
                                                               '_ignore'))
    cb_command_lib.ExtractFiles(IsA(str)).AndReturn('/tmp/firmware_dir')
    shutil.copy(IsA(str), IsA(str))
    shutil.copy(IsA(str), IsA(str))
    shutil.copy(IsA(str), IsA(str))
    cb_command_lib.RunCommand(IsA(list))
    cb_util_lib.CheckMd5(IsA(str), IsA(str)).AndReturn(False)
    self.mox.ReplayAll()
    self.assertRaises(BundlingError,
                      cb_command_lib.ExtractFirmware,
                      self.image_name,
                      self.firmware_dest,
                      self.mount_point)


if __name__ == "__main__":
  logging.basicConfig(level=logging.CRITICAL)
  unittest.main()
