#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for the cb_util_lib module."""

import hashlib
import logging
import mox
import os
import shutil
import tempfile
import unittest
import zipfile

import cb_command_lib
import cb_util_lib


def _CleanUp(obj):
  """Common logic to clean up file system state after a test.

  Assuming permission to delete files and directories specified.

  Args:
    obj: an object with members 'clean_files' and 'clean_dirs', lists
  """
  for file_to_clean in obj.clean_files:
    if os.path.exists(file_to_clean):
      os.remove(file_to_clean)
  for dir_to_clean in obj.clean_dirs:
    if os.path.isdir(dir_to_clean):
      shutil.rmtree(dir_to_clean)


class TestCheckMd5(unittest.TestCase):
  """Unit tests related to CheckMd5."""

  def setUp(self):
    self.clean_dirs = []

  def tearDown(self):
    _CleanUp(self)

  def testMd5Good(self):
    """Verify return value when checksums agree and are properly computed."""
    check_file = tempfile.NamedTemporaryFile()
    check_file.write('sample file content inserted here to be hashed')
    check_file.seek(0)
    # make a good md5 checksum
    hasher = hashlib.md5()
    for chunk in iter(lambda: check_file.read(128*hasher.block_size), ''):
      hasher.update(chunk)
    filename = check_file.name
    golden_file = tempfile.NamedTemporaryFile()
    golden_file.write(hasher.hexdigest() + '  ' + filename)
    golden_file.seek(0)
    md5filename = golden_file.name
    self.assertTrue(cb_util_lib.CheckMd5(filename, md5filename))
    self.clean_files = [filename, md5filename]

  def testMd5Bad(self):
    """Verify return value when checksums disagree."""
    check_file = tempfile.NamedTemporaryFile()
    check_file.write('sample file content inserted here to be hashed')
    check_file.seek(0)
    filename = check_file.name
    golden_file = tempfile.NamedTemporaryFile()
    golden_file.write('This_is_likely_not_the_checksum' + '  ' + filename)
    golden_file.seek(0)
    md5filename = golden_file.name
    self.assertFalse(cb_util_lib.CheckMd5(filename, md5filename))
    self.clean_files = [filename, md5filename]

  def testMd5FileEmpty(self):
    """Verify return value when md5 file empty."""
    check_file = tempfile.NamedTemporaryFile()
    filename = check_file.name
    golden_file = tempfile.NamedTemporaryFile()
    golden_file.write('')
    golden_file.seek(0)
    md5filename = golden_file.name
    self.assertFalse(cb_util_lib.CheckMd5(filename, md5filename))
    self.clean_files = [filename, md5filename]

  def testMd5FileBadFormat(self):
    """Verify return value when md5 file corrupt."""
    check_file = tempfile.NamedTemporaryFile()
    filename = check_file.name
    golden_file = tempfile.NamedTemporaryFile()
    golden_file.write('  ')
    golden_file.seek(0)
    md5filename = golden_file.name
    self.assertFalse(cb_util_lib.CheckMd5(filename, md5filename))
    self.clean_files = [filename, md5filename]

  def testNoCheckFile(self):
    """Verify return value when file to check does not exist."""
    filename = ''
    md5filename = ''
    self.assertFalse(cb_util_lib.CheckMd5(filename, md5filename))
    self.clean_files = []

  def testNoMd5File(self):
    """Verify return value when md5 checksum file does not exist."""
    check_file = tempfile.NamedTemporaryFile()
    filename = check_file.name
    md5filename = ''
    self.assertFalse(cb_util_lib.CheckMd5(filename, md5filename))
    self.clean_files = [filename]


class TestMakeMd5(unittest.TestCase):
  """Unit tests related to MakeMd5."""

  def setUp(self):
    self.clean_dirs = []

  def tearDown(self):
    _CleanUp(self)

  def testMd5Good(self):
    """Verify return value when md5 is successfully created."""
    read_file = tempfile.NamedTemporaryFile()
    read_file.write('sample file content inserted here to be hashed')
    read_file.seek(0)
    filename = read_file.name
    hash_file = tempfile.NamedTemporaryFile()
    md5filename = hash_file.name
    self.assertTrue(cb_util_lib.MakeMd5(filename, md5filename))
    self.clean_files = [filename, md5filename]

  def testNoReadFile(self):
    """Verify return value when file to read does not exist."""
    filename = ''
    md5filename = 'ignored'
    self.assertFalse(cb_util_lib.MakeMd5(filename, md5filename))
    self.clean_files = []

  def testHashFileOpenFails(self):
    """Verify return value when hash file creation fails."""
    read_file = tempfile.NamedTemporaryFile()
    filename = read_file.name
    md5filename = ''
    self.assertFalse(cb_util_lib.MakeMd5(filename, md5filename))
    self.clean_files = [filename]


class ZipExtract(unittest.TestCase):
  """Unit tests related to ZipExtract."""

  def setUp(self):
    # make a zip file and some content to zip
    myzipfile = tempfile.NamedTemporaryFile()
    self.zipname = myzipfile.name
    myzipfile.close()
    myfile = tempfile.NamedTemporaryFile()
    myfile.write('sample file content inserted here to be zipped')
    myfile.seek(0)
    self.filename = myfile.name.split(os.sep)[-1]
    zpf = zipfile.ZipFile(self.zipname, mode='w')
    zpf.write(myfile.name, arcname=self.filename)
    zpf.close()
    # default from cb_util_lib
    self.path = os.getcwd()

  def tearDown(self):
    _CleanUp(self)

  def testZipExtractWorksPathGiven(self):
    """Verify return value when all goes well and path provided."""
    path = tempfile.mkdtemp()
    self.assertTrue(cb_util_lib.ZipExtract(self.zipname, self.filename, path))
    self.clean_files = []
    self.clean_dirs = [path]

  def testZipExtractWorksNoPathGiven(self):
    """Verify return value when all goes well and no path provided."""
    self.assertTrue(cb_util_lib.ZipExtract(self.zipname, self.filename))
    self.clean_files = [os.path.join(self.path, self.filename)]
    self.clean_dirs = []

  def testFileNotInZip(self):
    """Verify return value when zip file does not contain file specified."""
    path = tempfile.mkdtemp()
    file_not_there = ''
    self.assertFalse(cb_util_lib.ZipExtract(self.zipname,
                                            file_not_there,
                                            path))
    self.clean_files = []
    self.clean_dirs = [path]


class TestMakeTar(unittest.TestCase):
  """Unit tests related to MakeTar."""

  def setUp(self):
    self.test_dir = tempfile.mkdtemp()

  def tearDown(self):
    _CleanUp(self)

  def testTarSuccessNoNameGiven(self):
    """Verify return value when all goes well."""
    test_file = tempfile.NamedTemporaryFile(prefix=self.test_dir)
    test_file.write('sample file content inserted here to be tarred')
    test_dest = tempfile.mkdtemp()
    folder_name = self.test_dir.split(os.sep)[-1]
    expected_name = os.path.join(test_dest, folder_name + '.tar.bz2')
    actual_name = cb_util_lib.MakeTar(self.test_dir, test_dest)
    self.assertEqual(expected_name, actual_name)
    self.clean_files = [test_file.name]
    self.clean_dirs = [self.test_dir, test_dest]

  def testTarSuccessNameGiven(self):
    """Verify return value when all goes well and name specified."""
    test_file = tempfile.NamedTemporaryFile(prefix=self.test_dir)
    test_file.write('sample file content inserted here to be tarred')
    test_dest = tempfile.mkdtemp()
    testname = 'testname'
    expected_name = os.path.join(test_dest, testname)
    actual_name = cb_util_lib.MakeTar(self.test_dir, test_dest, testname)
    self.assertEqual(expected_name, actual_name)
    self.clean_files = [test_file.name]
    self.clean_dirs = [self.test_dir, test_dest]

  def testTargetDoesNotExist(self):
    """Verify return value when target directory missing."""
    test_dir = ''
    test_dest = 'ignored'
    expected = None
    actual = cb_util_lib.MakeTar(test_dir, test_dest)
    self.assertEqual(expected, actual)
    self.clean_files = []
    self.clean_dirs = []

  def testTargetIsNotDirectory(self):
    """Verify return value when target directory is not a directory."""
    test_file_name = tempfile.NamedTemporaryFile().name
    test_dest = 'ignored'
    expected = None
    actual = cb_util_lib.MakeTar(test_file_name, test_dest)
    self.assertEqual(expected, actual)
    self.clean_files = [test_file_name]
    self.clean_dirs = []

  def testDestinationDoesNotExist(self):
    """Verify return value when destination directory missing."""
    test_file = tempfile.NamedTemporaryFile(prefix=self.test_dir)
    test_file.write('sample file content inserted here to be tarred')
    test_dest = ''
    expected = None
    actual = cb_util_lib.MakeTar(self.test_dir, test_dest)
    self.assertEqual(expected, actual)
    self.clean_files = [test_file.name]
    self.clean_dirs = [self.test_dir]

  def testDestinationIsNotDirectory(self):
    """Verify return value when destination directory is not a directory."""
    test_file_name = tempfile.NamedTemporaryFile().name
    expected = None
    actual = cb_util_lib.MakeTar(self.test_dir, test_file_name)
    self.assertEqual(expected, actual)
    self.clean_files = [test_file_name]
    self.clean_dirs = [self.test_dir]

  def testDestinationIsNotWritable(self):
    """Verify return value when destination directory is not writable."""
    # pick a directory with restricted access
    test_dest = '/usr'
    expected = None
    actual = cb_util_lib.MakeTar(self.test_dir, test_dest)
    self.assertEqual(expected, actual)
    self.clean_files = []
    self.clean_dirs = [self.test_dir]


if __name__ == "__main__":
  logging.basicConfig(level=logging.CRITICAL)
  unittest.main()
