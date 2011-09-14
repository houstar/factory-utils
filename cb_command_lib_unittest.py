#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for the cb_command_lib module."""

import cb_command_lib
import cb_constants
import logging
import mox
import os
import shutil
import tempfile
import unittest

from cb_util import CommandResult


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
  """Common logic to assert an error while listing firmware.

  Args:
    obj: an instance of mox.MoxTestBase pertaining to ListFirmware
  """
  obj.mox.StubOutWithMock(os.path, 'exists')
  obj.mox.StubOutWithMock(cb_command_lib, 'RunCommand')
  os.path.exists(mox.IsA(str)).AndReturn(True)
  cb_command_lib.RunCommand(mox.IsA(list),
                            redirect_stdout=True).AndReturn(obj.mock_cres)
  obj.mox.ReplayAll()
  obj.assertRaises(cb_constants.BundlingError,
                   cb_command_lib.ListFirmware,
                   obj.image_name,
                   obj.cros_fw)


def _AssertInstallCgptError(obj):
  """Common logic to assert an error while installing cgpt utility."""
  obj.mox.ReplayAll()
  obj.assertRaises(cb_constants.BundlingError,
                   cb_command_lib.InstallCgpt,
                   obj.index_page,
                   obj.force)


def _AssertConvertRecoveryError(obj):
  """Common logic to assert an error while converting recovery image.

  Args:
    obj: an instance of mox.MoxTestBase pertaining to ConvertRecoveryToSsd
  """
  obj.mox.ReplayAll()

  obj.assertRaises(cb_constants.BundlingError,
                   cb_command_lib.ConvertRecoveryToSsd,
                   obj.image_name,
                   obj)


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
    self.mock_cres = CommandResult()
    self.mock_cres.output = 'uudecode present'
    # do not need to clean up empty temporary file
    self.clean_dirs = [self.firmware_dest]

  def tearDown(self):
    _CleanUp(self)

  def testEnvironmentIsGood(self):
    """Verify return value when environment is all good."""
    os.getcwd().AndReturn('/home/$USER/chromiumos/src/scripts')
    cb_command_lib.RunCommand(mox.IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    self.assertTrue(cb_command_lib.CheckEnvironment(self.image_name,
                                                    self.firmware_dest,
                                                    self.mount_point))

  def testNotInScriptsDirectory(self):
    """Verify return value when script not run from <cros_root/src/scripts."""
    os.getcwd().AndReturn('/home/$USER/chromiumos/src/scripts/lib')
    cb_command_lib.RunCommand(mox.IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    self.assertFalse(cb_command_lib.CheckEnvironment(self.image_name,
                                                     self.firmware_dest,
                                                     self.mount_point))

  def testNoUudecode(self):
    """Verify return value when uudecode not present."""
    os.getcwd().AndReturn('/home/$USER/chromiumos/src/scripts')
    self.mock_cres.output = ''
    cb_command_lib.RunCommand(mox.IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    self.assertFalse(cb_command_lib.CheckEnvironment(self.image_name,
                                                     self.firmware_dest,
                                                     self.mount_point))

  def testSsdDoesNotExist(self):
    """Verify return value when given ssd image file not present."""
    self.image_name = ''
    os.getcwd().AndReturn('/home/$USER/chromiumos/src/scripts')
    cb_command_lib.RunCommand(mox.IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    self.assertFalse(cb_command_lib.CheckEnvironment(self.image_name,
                                                     self.firmware_dest,
                                                     self.mount_point))

  def testBadSsdName(self):
    """Verify return value when given ssd image has bad name."""
    self.image = tempfile.NamedTemporaryFile(suffix='recovery.bin')
    os.getcwd().AndReturn('/home/$USER/chromiumos/src/scripts')
    cb_command_lib.RunCommand(mox.IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    self.assertFalse(cb_command_lib.CheckEnvironment(self.image_name,
                                                     self.firmware_dest,
                                                     self.mount_point))

  def testFirmwareDestinationDoesNotExist(self):
    """Verify return value when environment is all good."""
    self.firmware_dest = ''
    os.getcwd().AndReturn('/home/$USER/chromiumos/src/scripts')
    cb_command_lib.RunCommand(mox.IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    self.assertFalse(cb_command_lib.CheckEnvironment(self.image_name,
                                                     self.firmware_dest,
                                                     self.mount_point))

  def testFirmwareDestinationNotWritable(self):
    """Verify return value when firmware destination directory not writable."""
    self.mox.StubOutWithMock(os, 'access')
    os.getcwd().AndReturn('/home/$USER/chromiumos/src/scripts')
    cb_command_lib.RunCommand(mox.IsA(list),
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
    cb_command_lib.RunCommand(mox.IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    self.assertFalse(cb_command_lib.CheckEnvironment(self.image_name,
                                                     self.firmware_dest,
                                                     self.mount_point))

  def testMountPointNotEmpty(self):
    """Verify return value when provided mount point is not empty."""
    self.mox.StubOutWithMock(os, 'listdir')
    os.getcwd().AndReturn('/home/$USER/chromiumos/src/scripts')
    cb_command_lib.RunCommand(mox.IsA(list),
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
    os.path.exists(mox.IsA(str)).AndReturn(True)
    cb_command_lib.RunCommand(mox.IsA(list))
    self.mox.ReplayAll()
    cb_command_lib.UploadToGsd(filename)

  def testNoFileGiven(self):
    """Verify error raised when no file given to upload."""
    filename = ''
    self.assertRaises(cb_constants.BundlingError,
                      cb_command_lib.UploadToGsd, filename)

  def testFileDoesNotExist(self):
    """Verify error raised when file given to upload does not exist."""
    filename = 'fakefilename'
    self.mox.StubOutWithMock(os.path, 'exists')
    os.path.exists(mox.IsA(str)).AndReturn(False)
    self.mox.ReplayAll()
    self.assertRaises(cb_constants.BundlingError,
                      cb_command_lib.UploadToGsd, filename)


class TestListFirmware(mox.MoxTestBase):
  """Unit tests related to ListFirmware."""

  def setUp(self):
    self.mox = mox.Mox()
    self.image_name = 'ssd_name_here.bin'
    self.cros_fw = 'chromeos-firmwareupdate'
    self.mock_cres = CommandResult()

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
    os.path.exists(mox.IsA(str)).AndReturn(True)
    cb_command_lib.RunCommand(mox.IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    expected = (ec_new_name, bios_new_name)
    actual = cb_command_lib.ListFirmware(self.image_name, self.cros_fw)
    self.assertEqual(expected, actual)

  def testCrosFwDoesNotExist(self):
    """Verify error when provided script name is bad."""
    self.cros_fw = ''
    self.assertRaises(cb_constants.BundlingError,
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
    os.path.exists(mox.IsA(str)).AndReturn(True)
    cb_command_lib.RunCommand(mox.IsA(list),
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
    self.mock_cres = CommandResult()
    self.mox.StubOutWithMock(os.path, 'exists')
    self.mox.StubOutWithMock(cb_command_lib, 'RunCommand')

  def testExtractFilesSuccess(self):
    """Verify return value when all goes well."""
    self.mock_cres.output = 'Files extracted to ' + self.fw_dir
    os.path.exists(self.cros_fw).AndReturn(True)
    cb_command_lib.RunCommand(mox.IsA(list),
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
    cb_command_lib.RunCommand(mox.IsA(list),
                              redirect_stdout=True).AndReturn(self.mock_cres)
    self.mox.ReplayAll()
    expected = None
    actual = cb_command_lib.ExtractFiles(self.cros_fw)
    self.assertEqual(expected, actual)

  def testTmpDirectoryDoesNotExist(self):
    """Verify return value when extractor fails."""
    self.mock_cres.output = 'Lying that files were extracted to ' + self.fw_dir
    os.path.exists(self.cros_fw).AndReturn(True)
    cb_command_lib.RunCommand(mox.IsA(list),
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
    self.mox.StubOutWithMock(cb_command_lib, 'CheckMd5')


  def testExtractFirmwareSuccess(self):
    """Verify behavior of quiet success when all goes well."""
    cb_command_lib.CheckEnvironment(self.image_name,
                                    self.firmware_dest,
                                    self.mount_point).AndReturn(True)
    cb_command_lib.RunCommand(mox.IsA(list))
    os.path.exists(self.mount_point).AndReturn(True)
    os.listdir(self.mount_point).AndReturn(['stuff', 'is', 'here'])
    cb_command_lib.ListFirmware(mox.IsA(str), mox.IsA(str)).AndReturn(
        ('ec_name', 'bios_name'))
    cb_command_lib.ExtractFiles(mox.IsA(str)).AndReturn('/tmp/firmware_dir')
    shutil.copy(mox.IsA(str), mox.IsA(str))
    shutil.copy(mox.IsA(str), mox.IsA(str))
    shutil.copy(mox.IsA(str), mox.IsA(str))
    cb_command_lib.RunCommand(mox.IsA(list))
    cb_command_lib.CheckMd5(mox.IsA(str), mox.IsA(str)).AndReturn(True)
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
    self.assertRaises(cb_constants.BundlingError,
                      cb_command_lib.ExtractFirmware,
                      self.image_name,
                      self.firmware_dest,
                      self.mount_point)

  def testMountSsdFailsMountPointNotThere(self):
    """Verify error when SSD image is not mounted."""
    cb_command_lib.CheckEnvironment(self.image_name,
                                    self.firmware_dest,
                                    self.mount_point).AndReturn(True)
    cb_command_lib.RunCommand(mox.IsA(list))
    os.path.exists(self.mount_point).AndReturn(False)
    cb_command_lib.RunCommand(mox.IsA(list))
    self.mox.ReplayAll()
    self.assertRaises(cb_constants.BundlingError,
                      cb_command_lib.ExtractFirmware,
                      self.image_name,
                      self.firmware_dest,
                      self.mount_point)

  def testMountSsdFailsMountPointEmpty(self):
    """Verify error when SSD image is not mounted."""
    cb_command_lib.CheckEnvironment(self.image_name,
                                    self.firmware_dest,
                                    self.mount_point).AndReturn(True)
    cb_command_lib.RunCommand(mox.IsA(list))
    os.path.exists(self.mount_point).AndReturn(True)
    os.listdir(self.mount_point).AndReturn([])
    cb_command_lib.RunCommand(mox.IsA(list))
    self.mox.ReplayAll()
    self.assertRaises(cb_constants.BundlingError,
                      cb_command_lib.ExtractFirmware,
                      self.image_name,
                      self.firmware_dest,
                      self.mount_point)

  def testFirmwareExtractionFails(self):
    """Verify error when firmware extraction fails."""
    cb_command_lib.CheckEnvironment(self.image_name,
                                    self.firmware_dest,
                                    self.mount_point).AndReturn(True)
    cb_command_lib.RunCommand(mox.IsA(list))
    os.path.exists(self.mount_point).AndReturn(True)
    os.listdir(self.mount_point).AndReturn(['stuff', 'is', 'here'])
    cb_command_lib.ListFirmware(mox.IsA(str), mox.IsA(str)).AndReturn(
        ('_ignore', '_ignore'))
    cb_command_lib.ExtractFiles(mox.IsA(str))
    cb_command_lib.RunCommand(mox.IsA(list))
    self.mox.ReplayAll()
    self.assertRaises(cb_constants.BundlingError,
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
    cb_command_lib.RunCommand(mox.IsA(list))
    os.path.exists(self.mount_point).AndReturn(True)
    os.listdir(self.mount_point).AndReturn(['stuff', 'is', 'here'])
    cb_command_lib.ListFirmware(mox.IsA(str), mox.IsA(str)).AndReturn(
        ('_ignore', '_ignore'))
    cb_command_lib.ExtractFiles(mox.IsA(str)).AndReturn('/tmp/firmware_dir')
    shutil.copy(mox.IsA(str), mox.IsA(str))
    shutil.copy(mox.IsA(str), mox.IsA(str))
    shutil.copy(mox.IsA(str), mox.IsA(str))
    cb_command_lib.RunCommand(mox.IsA(list))
    cb_command_lib.CheckMd5(mox.IsA(str), mox.IsA(str)).AndReturn(False)
    self.mox.ReplayAll()
    self.assertRaises(cb_constants.BundlingError,
                      cb_command_lib.ExtractFirmware,
                      self.image_name,
                      self.firmware_dest,
                      self.mount_point)


class TestHandleGitExists(mox.MoxTestBase):
  """Unit tests related to HandleGitExists."""

  def setUp(self):
    self.mox = mox.Mox()
    self.force = False
    self.mox.StubOutWithMock(os.path, 'exists')
    self.mox.StubOutWithMock(cb_command_lib, 'AskUserConfirmation')
    self.mox.StubOutWithMock(shutil, 'rmtree')
    self.mox.StubOutWithMock(os, 'mkdir')

  def testGitDoesNotExist(self):
    """Verify behavior when no git directory exists."""
    os.path.exists(cb_constants.GITDIR).AndReturn(False)
    os.mkdir(cb_constants.GITDIR)
    self.mox.ReplayAll()
    cb_command_lib.HandleGitExists(self.force)

  def testGitExistsNoForceUserConfirmsOverwrite(self):
    """Verify behavior when git files exist, user confirms overwrite."""
    os.path.exists(cb_constants.GITDIR).AndReturn(True)
    cb_command_lib.AskUserConfirmation(mox.IsA(str)).AndReturn(True)
    shutil.rmtree(cb_constants.GITDIR)
    os.mkdir(cb_constants.GITDIR)
    self.mox.ReplayAll()
    cb_command_lib.HandleGitExists(self.force)

  def testGitExistsNoForceNoConfirm(self):
    """Verify error when git files exist, no overwrite confirmation."""
    os.path.exists(cb_constants.GITDIR).AndReturn(True)
    cb_command_lib.AskUserConfirmation(mox.IsA(str)).AndReturn(False)
    self.mox.ReplayAll()
    self.assertRaises(cb_constants.BundlingError,
                      cb_command_lib.HandleGitExists,
                      self.force)

  def testGitExistsForceOverwrite(self):
    """Verify behavior when git files exist, script options allow overwrite."""
    self.force = True
    os.path.exists(cb_constants.GITDIR).AndReturn(True)
    shutil.rmtree(cb_constants.GITDIR)
    os.mkdir(cb_constants.GITDIR)
    self.mox.ReplayAll()
    cb_command_lib.HandleGitExists(self.force)


class TestHandleSsdExists(mox.MoxTestBase):
  """Unit tests related to HandleSsdExists."""

  def setUp(self):
    self.mox = mox.Mox()
    self.ssd_name = '/path/to/ssd_image'
    self.force = False
    self.mox.StubOutWithMock(os.path, 'exists')
    self.mox.StubOutWithMock(cb_command_lib, 'AskUserConfirmation')

  def testSsdDoesNotExist(self):
    """Verify behavior when no ssd image exists."""
    os.path.exists(self.ssd_name).AndReturn(False)
    self.mox.ReplayAll()
    cb_command_lib.HandleSsdExists(self.ssd_name, self.force)

  def testSsdExistsNoForceUserConfirmsOverwrite(self):
    """Verify behavior when ssd image exists, user confirms overwrite."""
    os.path.exists(self.ssd_name).AndReturn(True)
    cb_command_lib.AskUserConfirmation(mox.IsA(str)).AndReturn(True)
    self.mox.ReplayAll()
    cb_command_lib.HandleSsdExists(self.ssd_name, self.force)

  def testSsdExistsNoForceNoConfirm(self):
    """Verify error when ssd image exists, no overwrite confirmation."""
    os.path.exists(self.ssd_name).AndReturn(True)
    cb_command_lib.AskUserConfirmation(mox.IsA(str)).AndReturn(False)
    self.mox.ReplayAll()
    self.assertRaises(cb_constants.BundlingError,
                      cb_command_lib.HandleSsdExists,
                      self.ssd_name,
                      self.force)

  def testSsdExistsForceOverwrite(self):
    """Verify behavior when ssd exists, script options allow overwrite."""
    self.force = True
    os.path.exists(self.ssd_name).AndReturn(True)
    self.mox.ReplayAll()
    cb_command_lib.HandleSsdExists(self.ssd_name, self.force)


class TestInstallCgpt(mox.MoxTestBase):
  """Unit tests related to InstallCgpt."""

  def setUp(self):
    self.mox = mox.Mox()
    self.index_page = 'index_page'
    self.force = False
    self.mox.StubOutWithMock(cb_command_lib, 'Download')
    self.mox.StubOutWithMock(cb_command_lib, 'ZipExtract')
    self.mox.StubOutWithMock(os.path, 'exists')
    self.mox.StubOutWithMock(cb_command_lib, 'AskUserConfirmation')
    self.mox.StubOutWithMock(cb_command_lib, 'MoveCgpt')

  def testAuGenDownloadFails(self):
    """Verify error when download of au-generator zip fails."""
    cb_command_lib.Download(mox.IsA(str)).AndReturn(False)
    _AssertInstallCgptError(self)

  def testExtractCgptFails(self):
    """Verify error when cgpt is not extracted from au-generator zip."""
    cb_command_lib.Download(mox.IsA(str)).AndReturn(True)
    cb_command_lib.ZipExtract(
      mox.IsA(str),
      'cgpt',
      path=cb_constants.WORKDIR).AndReturn(False)
    _AssertInstallCgptError(self)

  def testCgptExistsNoForceNoConfirm(self):
    """Verify error when cgpt already exists at desired location."""
    cb_command_lib.Download(mox.IsA(str)).AndReturn(True)
    cb_command_lib.ZipExtract(
      mox.IsA(str),
      'cgpt',
      path=cb_constants.WORKDIR).AndReturn(True)
    os.path.exists(mox.IsA(str)).AndReturn(True)
    cb_command_lib.AskUserConfirmation(mox.IsA(str)).AndReturn(False)
    _AssertInstallCgptError(self)

  def testCgptExistsNoForceUserConfirmsOverwrite(self):
    """Verify behavior when cgpt already exists and user confirms overwrite."""
    cb_command_lib.Download(mox.IsA(str)).AndReturn(True)
    cb_command_lib.ZipExtract(
      mox.IsA(str),
      'cgpt',
      path=cb_constants.WORKDIR).AndReturn(True)
    os.path.exists(mox.IsA(str)).AndReturn(True)
    cb_command_lib.AskUserConfirmation(mox.IsA(str)).AndReturn(True)
    cb_command_lib.MoveCgpt(mox.IsA(str), mox.IsA(str))
    self.mox.ReplayAll()
    cb_command_lib.InstallCgpt(self.index_page, self.force)

  def testCgptExistsForceOverwrite(self):
    """Verify behavior when cgpt exists and script input allows overwrite."""
    self.force = True
    cb_command_lib.Download(mox.IsA(str)).AndReturn(True)
    cb_command_lib.ZipExtract(
      mox.IsA(str),
      'cgpt',
      path=cb_constants.WORKDIR).AndReturn(True)
    os.path.exists(mox.IsA(str)).AndReturn(True)
    cb_command_lib.MoveCgpt(mox.IsA(str), mox.IsA(str))
    self.mox.ReplayAll()
    cb_command_lib.InstallCgpt(self.index_page, self.force)

  def testCgptDoesNotExist(self):
    """Verify behavior when cgpt can be installed fresh."""
    cb_command_lib.Download(mox.IsA(str)).AndReturn(True)
    cb_command_lib.ZipExtract(
      mox.IsA(str),
      'cgpt',
      path=cb_constants.WORKDIR).AndReturn(True)
    os.path.exists(mox.IsA(str)).AndReturn(False)
    cb_command_lib.MoveCgpt(mox.IsA(str), mox.IsA(str))
    self.mox.ReplayAll()
    cb_command_lib.InstallCgpt(self.index_page, self.force)


class TestConvertRecoveryToSsd(mox.MoxTestBase):
  """Unit tests related to ConvertRecoveryToSsd."""

  def setUp(self):
    self.mox = mox.Mox()
    self.image_name = '/abs/path/to/recovery.bin'
    self.ssd_name = self.image_name.replace('recovery', 'ssd')
    self.board = 'board-name'
    self.recovery = 'rec_no/rec_channel/rec_key'
    self.force = False
    self.full_ssd = True
    self.chromeos_root = '/tmp/cros/src/scripts'
    self.index_page = 'index_page'
    self.rec_pat = 'recovery_image_name_pattern'
    self.rec_url = 'recovery_image_url'
    self.zip_url = 'zip_url'
    self.mox.StubOutWithMock(cb_command_lib, 'HandleGitExists')
    self.mox.StubOutWithMock(cb_command_lib, 'RunCommand')
    self.mox.StubOutWithMock(cb_command_lib, 'ResolveRecoveryUrl')
    self.mox.StubOutWithMock(cb_command_lib, 'DetermineUrl')
    self.mox.StubOutWithMock(cb_command_lib, 'Download')
    self.mox.StubOutWithMock(cb_command_lib, 'HandleSsdExists')
    self.mox.StubOutWithMock(cb_command_lib, 'InstallCgpt')

  def testConvertRecoveryToSsdSuccess(self):
    """Verify return value when recovery to full ssd conversion succeeds."""
    cb_command_lib.HandleGitExists(self.force)
    cb_command_lib.RunCommand(mox.IsA(list))
    cb_command_lib.ResolveRecoveryUrl(
        self.board, self.recovery, alt_naming=0).AndReturn(
            (self.rec_url, self.index_page))
    cb_command_lib.DetermineUrl(self.index_page,
                            mox.IsA(str)).AndReturn(self.zip_url)
    cb_command_lib.Download(self.zip_url).AndReturn(True)
    cb_command_lib.HandleSsdExists(self.ssd_name, self.force)
    cb_command_lib.InstallCgpt(self.index_page, self.force)
    cb_command_lib.RunCommand(mox.IsA(list))
    self.mox.ReplayAll()
    actual = cb_command_lib.ConvertRecoveryToSsd(self.image_name, self)
    self.assertEqual(self.ssd_name, actual)

  def testGitExistsNotHandled(self):
    """Verify error when git files exist, user does not confirm overwrite."""
    cb_command_lib.HandleSsdExists(self.ssd_name, self.force)
    cb_command_lib.HandleGitExists(self.force).AndRaise(
        cb_constants.BundlingError(''))
    _AssertConvertRecoveryError(self)

  def testRecoveryNameNotResolved(self):
    """Verify error when recovery image url cannot be determined."""
    cb_command_lib.HandleSsdExists(self.ssd_name, self.force)
    cb_command_lib.HandleGitExists(self.force)
    cb_command_lib.RunCommand(mox.IsA(list))
    cb_command_lib.ResolveRecoveryUrl(
        self.board, self.recovery, alt_naming=0).AndReturn(
            (None, None))
    _AssertConvertRecoveryError(self)

  def testCannotDetermineBaseImageZipUrl(self):
    """Verify error when name of zip with base image cannot be determined."""
    cb_command_lib.HandleSsdExists(self.ssd_name, self.force)
    cb_command_lib.HandleGitExists(self.force)
    cb_command_lib.RunCommand(mox.IsA(list))
    cb_command_lib.ResolveRecoveryUrl(
        self.board, self.recovery, alt_naming=0).AndReturn(
            (self.rec_url, self.index_page))
    cb_command_lib.DetermineUrl(self.index_page, mox.IsA(str)).AndReturn(None)
    _AssertConvertRecoveryError(self)

  def testBaseImageZipDownloadFails(self):
    """Verify error when zip containing base image is not downloaded."""
    cb_command_lib.HandleSsdExists(self.ssd_name, self.force)
    cb_command_lib.HandleGitExists(self.force)
    cb_command_lib.RunCommand(mox.IsA(list))
    cb_command_lib.ResolveRecoveryUrl(
        self.board, self.recovery, alt_naming=0).AndReturn(
            (self.rec_url, self.index_page))
    cb_command_lib.DetermineUrl(self.index_page, mox.IsA(str)).AndReturn(
        self.zip_url)
    cb_command_lib.Download(self.zip_url).AndReturn(False)
    _AssertConvertRecoveryError(self)

  def testSsdImageExistsNoConfirm(self):
    """Verify error when SSD image exists, user does not confirm overwrite."""
    cb_command_lib.HandleSsdExists(self.ssd_name, self.force).AndRaise(
        cb_constants.BundlingError(''))
    _AssertConvertRecoveryError(self)

  def testInstallCgptFails(self):
    """Verify error when installing cgpt utility fails."""
    cb_command_lib.HandleGitExists(self.force)
    cb_command_lib.RunCommand(mox.IsA(list))
    cb_command_lib.ResolveRecoveryUrl(
        self.board, self.recovery, alt_naming=0).AndReturn(
            (self.rec_url, self.index_page))
    cb_command_lib.DetermineUrl(self.index_page, mox.IsA(str)).AndReturn(
        self.zip_url)
    cb_command_lib.Download(self.zip_url).AndReturn(True)
    cb_command_lib.HandleSsdExists(self.ssd_name, self.force)
    cb_command_lib.InstallCgpt(self.index_page, self.force).AndRaise(
        cb_constants.BundlingError(''))
    _AssertConvertRecoveryError(self)


if __name__ == "__main__":
  logging.basicConfig(level=logging.CRITICAL)
  unittest.main()
