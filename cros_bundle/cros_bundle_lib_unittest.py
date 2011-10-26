#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for the cros_bundle_lib module."""

import __builtin__
import cros_bundle_lib
import mox
import optparse
import os
import sys
import tempfile
import unittest

from cb_constants import BundlingError, WORKDIR
from cros_bundle import CreateParser


# TODO(tgao): add tests for CheckBundleInputs and MakeFactoryBundle

class TestMakeMd5Sums(mox.MoxTestBase):
  """Tests related to MakeMd5Sums."""

  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(__builtin__, 'open')
    self.mox.StubOutWithMock(cros_bundle_lib, 'GenerateMd5')
    self.mox.StubOutWithMock(os, 'listdir')

    self.bundle_dir = 'bundle_dir'
    self.dirname = 'dir'
    self.bundle_dirname = os.path.join(self.bundle_dir, self.dirname)
    self.dir_list = [self.dirname]
    self.file_list = ['file.bin']
    self.file_md5 = 'file_checksum.md5'
    self.md5filename = os.path.join(self.bundle_dir, self.file_md5)
    self.md5sum = 'md5sum'
    self.test_file = tempfile.NamedTemporaryFile()

  def testMakeMd5SumsGoodOneDirOneFile(self):
    """Verify success with one directory and one file."""
    expected = ['md5sum  ./dir/file.bin\n']

    os.listdir(self.bundle_dir).AndReturn(self.dir_list)
    os.listdir(self.bundle_dirname).AndReturn(self.file_list)
    open(self.md5filename, 'w').AndReturn(self.test_file)
    cros_bundle_lib.GenerateMd5(
        'bundle_dir/dir/file.bin').AndReturn(self.md5sum)
    self.mox.ReplayAll()
    self.assertEqual(expected, cros_bundle_lib.MakeMd5Sums(self.bundle_dir))

  def testMakeMd5SumsGoodOneDirTwoFiles(self):
    """Verify success with one directory and two files."""
    expected = ['md5sum  ./dir/file1.bin\n', 'md5sum  ./dir/file2.fd\n']
    self.file_list = ['file1.bin', 'file2.fd']

    os.listdir(self.bundle_dir).AndReturn(self.dir_list)
    os.listdir(self.bundle_dirname).AndReturn(self.file_list)
    open(self.md5filename, 'w').AndReturn(self.test_file)
    cros_bundle_lib.GenerateMd5(
        'bundle_dir/dir/file1.bin').AndReturn(self.md5sum)
    cros_bundle_lib.GenerateMd5(
        'bundle_dir/dir/file2.fd').AndReturn(self.md5sum)
    self.mox.ReplayAll()
    self.assertEqual(expected, cros_bundle_lib.MakeMd5Sums(self.bundle_dir))

  def testMakeMd5SumsGoodTwoDirsOneFileEach(self):
    """Verify success with two directories and one file each."""
    expected = ['md5sum  ./dir1/file.bin\n', 'md5sum  ./dir2/file.bin\n']
    self.dir_list = ['dir1', 'dir2']

    os.listdir(self.bundle_dir).AndReturn(self.dir_list)
    os.listdir(os.path.join(self.bundle_dir, 'dir1')).AndReturn(self.file_list)
    os.listdir(os.path.join(self.bundle_dir, 'dir2')).AndReturn(self.file_list)
    open(self.md5filename, 'w').AndReturn(self.test_file)
    cros_bundle_lib.GenerateMd5(
        'bundle_dir/dir1/file.bin').AndReturn(self.md5sum)
    cros_bundle_lib.GenerateMd5(
        'bundle_dir/dir2/file.bin').AndReturn(self.md5sum)
    self.mox.ReplayAll()
    self.assertEqual(expected, cros_bundle_lib.MakeMd5Sums(self.bundle_dir))

  def testMakeMd5SumsFailGenerateMd5RaisesError(self):
    """Error when failed to generate Md5 checksum of a file."""
    os.listdir(self.bundle_dir).AndReturn(self.dir_list)
    os.listdir(self.bundle_dirname).AndReturn(self.file_list)
    open(self.md5filename, 'w').AndReturn(self.test_file)
    cros_bundle_lib.GenerateMd5(
        'bundle_dir/dir/file.bin').AndReturn(None)
    self.mox.ReplayAll()
    self.assertRaises(BundlingError,
                      cros_bundle_lib.MakeMd5Sums, self.bundle_dir)

  def testMakeMd5SumsFailWriteOutputRaisesError(self):
    """Error when failed to open md5sum output file for write."""
    os.listdir(self.bundle_dir).AndReturn(self.dir_list)
    os.listdir(self.bundle_dirname).AndReturn(self.file_list)
    open(self.md5filename, 'w').AndRaise(IOError)
    self.mox.ReplayAll()
    self.assertRaises(BundlingError,
                      cros_bundle_lib.MakeMd5Sums, self.bundle_dir)


class TestGetResourceUrlAndPath(mox.MoxTestBase):
  """Tests related to _GetResourceUrlAndPath."""

  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(cros_bundle_lib, 'DetermineThenDownloadCheckMd5')
    self.mox.StubOutWithMock(cros_bundle_lib, 'GetFactoryName')

  def testGetResourceUrlAndPath(self):
    test_url = 'url'
    test_pat = 'pat'
    test_desc = 'desc'
    test_path = 'path'

    cros_bundle_lib.GetFactoryName('board', 'factory', 0).AndReturn(
        (test_url, test_pat))
    cros_bundle_lib.DetermineThenDownloadCheckMd5(
        test_url, test_pat, WORKDIR, test_desc).AndReturn(test_path)
    self.mox.ReplayAll()
    actual_url, actual_path = cros_bundle_lib._GetResourceUrlAndPath(
        test_desc, cros_bundle_lib.GetFactoryName, 'board', 'factory', 0
        )
    self.assertEqual(test_url, actual_url)
    self.assertEqual(test_path, actual_path)


class TestHandleFactoryImageAndShim(mox.MoxTestBase):
  """Tests related to _HandleFactoryImageAndShim."""

  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(cros_bundle_lib, 'ConvertRecoveryToSsd')
    self.mox.StubOutWithMock(cros_bundle_lib, 'DetermineThenDownloadCheckMd5')
    self.mox.StubOutWithMock(cros_bundle_lib, 'DetermineUrl')
    self.mox.StubOutWithMock(cros_bundle_lib, 'Download')
    self.mox.StubOutWithMock(cros_bundle_lib, 'GetFactoryName')
    self.mox.StubOutWithMock(cros_bundle_lib, 'GetShimName')
    self.mox.StubOutWithMock(cros_bundle_lib, 'ZipExtract')
    self.mox.StubOutWithMock(os.path, 'exists')

    self.options = self.mox.CreateMock(optparse.Values)
    self.options.board = 'board'
    self.options.factory = 'factory'
    self.options.shim = 'shim'

    self.alt_naming = 0
    self.fac_det_url = 'fac_det_url/file'
    self.fac_name = os.path.join(WORKDIR, 'file')
    self.fac_pat = 'fac_pat'
    self.fac_url = 'fac_url'
    self.rec_url = 'rec_url'
    self.factorybin = os.path.join('factory_test',
                                   'chromiumos_factory_image.bin')
    self.absfactorybin = os.path.join(WORKDIR, self.factorybin)
    self.shim_name = 'shim_name'
    self.shim_pat = 'shim_pat'

    cros_bundle_lib.GetFactoryName(
        self.options.board, self.options.factory, self.alt_naming).AndReturn(
        (self.fac_url, self.fac_pat))

  def testHandleFactoryImageAndShimBadImageUrlRaisesError(self):
    """Error determining factory image URL."""
    cros_bundle_lib.DetermineUrl(self.fac_url, self.fac_pat).AndReturn(None)
    self.mox.ReplayAll()
    self.assertRaises(
        BundlingError, cros_bundle_lib._HandleFactoryImageAndShim,
        self.rec_url, self.options, self.alt_naming)

  def testHandleFactoryImageAndShimDownloadFailRaisesError(self):
    """Error downloading factory image."""
    cros_bundle_lib.DetermineUrl(
        self.fac_url, self.fac_pat).AndReturn(self.fac_det_url)
    os.path.exists(self.fac_name).AndReturn(False)
    cros_bundle_lib.Download(self.fac_det_url).AndReturn(False)
    self.mox.ReplayAll()
    self.assertRaises(
        BundlingError, cros_bundle_lib._HandleFactoryImageAndShim,
        self.rec_url, self.options, self.alt_naming)

  def testHandleFactoryImageAndShimExtractFailRaisesError(self):
    """Error extracting factory image."""
    cros_bundle_lib.DetermineUrl(
        self.fac_url, self.fac_pat).AndReturn(self.fac_det_url)
    os.path.exists(self.fac_name).AndReturn(True)
    os.path.exists(self.absfactorybin).AndReturn(False)
    cros_bundle_lib.ZipExtract(
        self.fac_name, self.factorybin, path=WORKDIR).AndReturn(False)
    self.mox.ReplayAll()
    self.assertRaises(
        BundlingError, cros_bundle_lib._HandleFactoryImageAndShim,
        self.rec_url, self.options, self.alt_naming)

  def testHandleFactoryImageAndShimGoodNoDownloadNoExtract(self):
    """Verify success with no image download or extraction."""
    expected = (self.absfactorybin, self.shim_name)

    cros_bundle_lib.DetermineUrl(
        self.fac_url, self.fac_pat).AndReturn(self.fac_det_url)
    os.path.exists(self.fac_name).AndReturn(True)
    os.path.exists(self.absfactorybin).AndReturn(True)
    cros_bundle_lib.GetShimName(
        self.options.board, self.options.shim, self.alt_naming).AndReturn(
        (None, self.shim_pat))
    cros_bundle_lib.DetermineThenDownloadCheckMd5(
        self.rec_url, self.shim_pat, WORKDIR, mox.IgnoreArg()).AndReturn(
        self.shim_name)
    self.mox.ReplayAll()
    actual = cros_bundle_lib._HandleFactoryImageAndShim(
        self.rec_url, self.options, self.alt_naming)
    self.assertEqual(expected, actual)

  def testHandleFactoryImageAndShimGoodDownloadAndExtract(self):
    """Verify success with image download and extraction."""
    expected = (self.absfactorybin, self.shim_name)

    cros_bundle_lib.DetermineUrl(
        self.fac_url, self.fac_pat).AndReturn(self.fac_det_url)
    os.path.exists(self.fac_name).AndReturn(False)
    cros_bundle_lib.Download(self.fac_det_url).AndReturn(True)
    os.path.exists(self.absfactorybin).AndReturn(False)
    cros_bundle_lib.ZipExtract(
        self.fac_name, self.factorybin, path=WORKDIR).AndReturn(True)
    cros_bundle_lib.GetShimName(
        self.options.board, self.options.shim, self.alt_naming).AndReturn(
        (None, self.shim_pat))
    cros_bundle_lib.DetermineThenDownloadCheckMd5(
        self.rec_url, self.shim_pat, WORKDIR, mox.IgnoreArg()).AndReturn(
        self.shim_name)
    self.mox.ReplayAll()
    actual = cros_bundle_lib._HandleFactoryImageAndShim(
        self.rec_url, self.options, self.alt_naming)
    self.assertEqual(expected, actual)


class TestFetchImages(mox.MoxTestBase):
  """Tests related to FetchImages."""

  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(cros_bundle_lib, 'ConvertRecoveryToSsd')
    self.mox.StubOutWithMock(cros_bundle_lib, '_GetResourceUrlAndPath')
    self.mox.StubOutWithMock(cros_bundle_lib, '_HandleFactoryImageAndShim')
    self.mox.StubOutWithMock(cros_bundle_lib, 'MakeMd5')

    self.options = self.mox.CreateMock(optparse.Values)
    self.options.board = 'board'
    self.options.board2 = 'board2'
    self.options.factory = 'factory'
    self.options.fsi = True
    self.options.recovery = 'recovery'
    self.options.recovery2 = 'recovery'
    self.options.release = 'release'
    self.options.release2 = 'release2'
    self.options.shim = 'shim'

    self.rec_name = 'rec_name'
    self.rec_name2 = 'rec_name2'
    self.rel_name = 'rel_name'
    self.rel_name2 = 'rel_name2'
    self.rec_url = 'rec_url'
    self.rec_url2 = 'rec_url2'
    self.rel_url = 'rel_url'
    self.rel_url2 = 'rel_url2'

    cros_bundle_lib._GetResourceUrlAndPath(
       mox.IgnoreArg(), cros_bundle_lib.GetRecoveryName, self.options.board,
       self.options.recovery, 0).AndReturn((self.rec_url, self.rec_name))

  def testFetchImagesWithOneRecoveryMd5FailRaisesError(self):
    """Error computing Md5 checksum of SSD image converted from recovery."""
    self.options.release = None
    cros_bundle_lib.ConvertRecoveryToSsd(
        self.rec_name, self.options).AndReturn(self.rel_name)
    cros_bundle_lib.MakeMd5(self.rel_name, 'rel_name.md5').AndReturn(False)
    self.mox.ReplayAll()
    self.assertRaises(BundlingError, cros_bundle_lib.FetchImages, self.options)

  def testFetchImagesGoodWithOneRecoveryFile(self):
    """Fetch success for one recovery file."""
    self.options.recovery2 = None
    self.options.release = None
    self.options.release2 = None
    expected = dict(ssd=self.rel_name, ssd2=None, recovery=self.rec_name,
                    recovery2=None)

    cros_bundle_lib.ConvertRecoveryToSsd(
        self.rec_name, self.options).AndReturn(self.rel_name)
    cros_bundle_lib.MakeMd5(self.rel_name, 'rel_name.md5').AndReturn(True)
    self.mox.ReplayAll()
    self.assertEqual(expected, cros_bundle_lib.FetchImages(self.options))

  def testFetchImagesGoodWithOneSetOfFiles(self):
    """Fetch success for one set of recovery/release files."""
    self.options.recovery2 = None
    self.options.release2 = None
    expected = dict(ssd=self.rel_name, ssd2=None, recovery=self.rec_name,
                    recovery2=None)

    cros_bundle_lib._GetResourceUrlAndPath(
       mox.IgnoreArg(), cros_bundle_lib.GetReleaseName, self.options.board,
       self.options.release, 0).AndReturn((self.rel_url, self.rel_name))
    self.mox.ReplayAll()
    self.assertEqual(expected, cros_bundle_lib.FetchImages(self.options))

  def testFetchImagesGoodWithOneSetOfFilesAndNotFsi(self):
    """Fetch success for one set of recovery/release files and non-FSI."""
    self.options.fsi = False
    self.options.recovery2 = None
    self.options.release2 = None
    absfactorybin = 'absfactorybin'
    shim_name = 'shim_name'
    expected = dict(ssd=self.rel_name, ssd2=None, recovery=self.rec_name,
                    recovery2=None, factorybin=absfactorybin, shim=shim_name)

    cros_bundle_lib._GetResourceUrlAndPath(
       mox.IgnoreArg(), cros_bundle_lib.GetReleaseName, self.options.board,
       self.options.release, 0).AndReturn((self.rel_url, self.rel_name))
    cros_bundle_lib._HandleFactoryImageAndShim(
        self.rec_url, self.options, 0).AndReturn((absfactorybin, shim_name))
    self.mox.ReplayAll()
    self.assertEqual(expected, cros_bundle_lib.FetchImages(self.options))

  def testFetchImagesGoodWithTwoSetsOfFiles(self):
    """Fetch success for two sets of recovery/release files."""
    expected = dict(ssd=self.rel_name, ssd2=self.rel_name2,
                    recovery=self.rec_name, recovery2=self.rec_name2)
    cros_bundle_lib._GetResourceUrlAndPath(
       mox.IgnoreArg(), cros_bundle_lib.GetReleaseName, self.options.board,
       self.options.release, 0).AndReturn((self.rel_url, self.rel_name))
    cros_bundle_lib._GetResourceUrlAndPath(
       mox.IgnoreArg(), cros_bundle_lib.GetReleaseName, self.options.board2,
       self.options.release2, 0).AndReturn((self.rel_url2, self.rel_name2))
    cros_bundle_lib._GetResourceUrlAndPath(
       mox.IgnoreArg(), cros_bundle_lib.GetRecoveryName, self.options.board2,
       self.options.recovery2, 0).AndReturn((self.rec_url2, self.rec_name2))
    self.mox.ReplayAll()
    self.assertEqual(expected, cros_bundle_lib.FetchImages(self.options))

  def testFetchImagesGoodWithOneReleaseTwoRecovery(self):
    """Fetch success for one release file and two recovery files."""
    self.options.release2 = None
    expected = dict(ssd=self.rel_name, ssd2=self.rel_name2,
                    recovery=self.rec_name, recovery2=self.rec_name2)
    cros_bundle_lib._GetResourceUrlAndPath(
       mox.IgnoreArg(), cros_bundle_lib.GetReleaseName, self.options.board,
       self.options.release, 0).AndReturn((self.rel_url, self.rel_name))
    cros_bundle_lib._GetResourceUrlAndPath(
       mox.IgnoreArg(), cros_bundle_lib.GetRecoveryName, self.options.board2,
       self.options.recovery2, 0).AndReturn((self.rec_url2, self.rec_name2))
    cros_bundle_lib.ConvertRecoveryToSsd(
        self.rec_name2, self.options).AndReturn(self.rel_name2)
    self.mox.ReplayAll()
    self.assertEqual(expected, cros_bundle_lib.FetchImages(self.options))


class TestCheckParseOptions(mox.MoxTestBase):
  """Tests related to CheckParseOptions."""

  def setUp(self):
    self.mox = mox.Mox()
    self.options = self.mox.CreateMock(optparse.Values)
    self.options.clean = True
    self.options.factory = True
    self.options.force = True
    self.options.fsi = True
    self.options.shim = True
    self.mox.StubOutWithMock(cros_bundle_lib, 'RunCommand')
    self.parser = CreateParser()

  def testCheckParseOptionsGoodWithForce(self):
    """Verify good input flags (including --force) does not raise error."""
    cros_bundle_lib.RunCommand(['sudo', '-v']).AndReturn(None)
    self.mox.ReplayAll()
    _ = cros_bundle_lib.CheckParseOptions(self.options, self.parser)
    # Nothing to assert here b/c the function has no return statement

  def testCheckParseOptionsGoodWithoutForce(self):
    """Verify good input flags (excluding --force) does not raise error."""
    self.options.force = False
    _ = cros_bundle_lib.CheckParseOptions(self.options, self.parser)


if __name__ == '__main__':
  unittest.main()
