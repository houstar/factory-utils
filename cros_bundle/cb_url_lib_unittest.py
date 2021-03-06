#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for the cb_url_lib module."""

import cb_url_lib
import formatter
import logging
import mox
import os
import unittest
import urllib
import tempfile

from cb_constants import BundlingError, IMAGE_GSD_BUCKET, IMAGE_GSD_PREFIX
from cb_util import CommandResult

from mox import IsA

_LINK_NAME = 'href_atrribute/of_a_link'


class UrlListerTest(unittest.TestCase):
  """Unit tests for the UrlLister class."""

  def setUp(self):
    self.givenformatter = formatter.NullFormatter()

  def testReset(self):
    """Tests the reset method of class UrlLister."""
    with open('testdata/test_page_one_link.html', 'r') as page:
      parser = cb_url_lib.UrlLister(self.givenformatter)
      parser.urls = ['a_fake_link', 'another_fake_link']
      parser.reset()
      parser.feed(page.read())
      parser.close()
      self.assertEqual([_LINK_NAME], parser.urls)

  def testStart_aNoLinks(self):
    """Verify behavior when no links exist on given page."""
    with open('testdata/test_page_no_links.html', 'r') as page:
      parser = cb_url_lib.UrlLister(self.givenformatter)
      parser.feed(page.read())
      parser.close()
      self.assertEqual([], parser.urls)

  def testStart_aOneLink(self):
    """Verify parsing when one link present."""
    with open('testdata/test_page_one_link.html', 'r') as page:
      parser = cb_url_lib.UrlLister(self.givenformatter)
      parser.feed(page.read())
      parser.close()
      self.assertEqual([_LINK_NAME], parser.urls)

  def testStart_aManyLinks(self):
    """Verify parsing when many links present."""
    with open('testdata/test_page_many_links.html', 'r') as page:
      parser = cb_url_lib.UrlLister(self.givenformatter)
      parser.feed(page.read())
      parser.close()
      # sample page links taken from real chromeos-images index page
      expected = ['/stable-channel/x86-alex/',
                  'ChromeOS-0.12.433.269-r72d7eaa2-b198-x86-alex.zip',
                  'ChromeOS-factory-0.12.433.269-r72d7eaa2-b198-x86-alex.zip']
      actual = parser.urls
      self.assertEqual(expected, actual)


class TestDetermineUrl(mox.MoxTestBase):
  """Unit tests related to DetermineUrl."""

  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(urllib, 'urlopen')
    self.mox.StubOutWithMock(cb_url_lib, 'RunCommand')
    self.url = 'test_url'
    self.pattern = ['chromeos', '.zip']
    self.http_url = IMAGE_GSD_PREFIX + '/test_url'
    self.gsd_url = IMAGE_GSD_BUCKET + '/test_url/*'
    self.gsd_pattern = ['chromeos', '.bin']

  def testHttpUrlGood(self):
    """Verify URL returned when page opens properly."""
    with open('testdata/test_page_many_links.html', 'r') as test_page:
      urllib.urlopen('test_url').AndReturn(test_page)
      self.mox.ReplayAll()
      expected = 'test_url/ChromeOS-0.12.433.269-r72d7eaa2-b198-x86-alex.zip'
      actual = cb_url_lib.DetermineUrl(self.url, self.pattern)
      self.assertEqual(expected, actual)

  def testHttpUrlBad(self):
    """Verify None returned when page fails to open properly."""
    urllib.urlopen('test_url').AndRaise(IOError)
    self.mox.ReplayAll()
    actual = cb_url_lib.DetermineUrl(self.url, self.pattern)
    self.assertEqual(None, actual)

  def testHttpUrlNoMatch(self):
    """Verify None returned when MatchUrl() returns None."""
    with open('testdata/test_page_no_links.html', 'r') as test_page:
      urllib.urlopen('test_url').AndReturn(test_page)
      self.mox.ReplayAll()
      actual = cb_url_lib.DetermineUrl(self.url, self.pattern)
      self.assertEqual(None, actual)

  def testGsdUrlGood(self):
    """Verify GSD URL returned when page opens properly."""
    with open('testdata/test_page_gsd_links.html', 'r') as test_page:
      test_result = CommandResult()
      test_result.output = test_page.read()
      test_result.returncode = 0

    cb_url_lib.RunCommand(['gsutil', 'ls', self.gsd_url], redirect_stdout=True,
                          redirect_stderr=True).AndReturn(test_result)
    self.mox.ReplayAll()
    expected = (
        'gs://chromeos-releases/stable-channel/x86-alex/0.12.433.269/'
        'chromeos_0.12.433.269_x86-alex_recovery_stable-channel_mp-v3.bin')
    actual = cb_url_lib.DetermineUrl(self.http_url, self.gsd_pattern)
    self.assertEqual(expected, actual)

  def testGsdUrlRunCommandError(self):
    """Verify None returned when RunCommand returns non-zero code."""
    test_result = CommandResult()
    test_result.returncode = -1

    cb_url_lib.RunCommand(['gsutil', 'ls', self.gsd_url], redirect_stdout=True,
                          redirect_stderr=True).AndReturn(test_result)
    self.mox.ReplayAll()
    actual = cb_url_lib.DetermineUrl(self.http_url, self.gsd_pattern)
    self.assertEqual(None, actual)

  def testGsdUrlNoMatch(self):
    """Verify None returned when MatchUrl() returns None."""
    with open('testdata/test_page_many_links.html', 'r') as test_page:
      test_result = CommandResult()
      test_result.output = test_page.read()
      test_result.returncode = 0

    cb_url_lib.RunCommand(['gsutil', 'ls', self.gsd_url], redirect_stdout=True,
                          redirect_stderr=True).AndReturn(test_result)
    self.mox.ReplayAll()
    actual = cb_url_lib.DetermineUrl(self.http_url, self.gsd_pattern)
    self.assertEqual(None, actual)


class TestMatchUrl(unittest.TestCase):
  """Unit tests related to MatchUrl."""

  def setUp(self):
    self.token_list = ['abc', '.bin']
    self.filename = 'abcdefghi.bin'

  def testNoMatch(self):
    """Verify behavior when no match exists."""
    url_list = ['abd.bin', 'acd.bin']
    actual = cb_url_lib.MatchUrl(url_list, self.token_list)
    self.assertEqual(None, actual)

  def testOneMatch(self):
    """Verify string returned upon a single good match."""
    url_list = ['abd.bin', 'acd.bin', self.filename]
    actual = cb_url_lib.MatchUrl(url_list, self.token_list)
    self.assertEqual(self.filename, actual)

  def testManyMatches(self):
    """verify string returned upon multiple good matches."""
    url_list = [self.filename, 'abc.bin', 'bdfhabc.bin']
    actual = cb_url_lib.MatchUrl(url_list, self.token_list)
    self.assertEqual(self.filename, actual)

  def testMatchUrlEmptyUrl(self):
    """Verify behavior when input url_list is empty."""
    self.assertFalse(cb_url_lib.MatchUrl([], self.token_list))

  def testMatchUrlEmptyTokenList(self):
    """Verify behavior when input token_list is empty."""
    self.assertFalse(cb_url_lib.MatchUrl(['url'], []))

  def testMatchUrlWithFullUrl(self):
    """Verify good match when input url is a full path."""
    test_url = os.path.join('http://domain.com', self.filename)
    self.assertTrue(cb_url_lib.MatchUrl([test_url], self.token_list))

  def testMatchUrlWithFilenameOnly(self):
    """Verify good match when input url is a filename (no path info)."""
    self.assertTrue(cb_url_lib.MatchUrl([self.filename], self.token_list))

  def testMatchUrlWithFilenameOnlyMixedCase(self):
    """Verify good match when input url is a filename (no path info)."""
    self.filename = 'aBcdEfgHI.biN'
    self.assertTrue(cb_url_lib.MatchUrl([self.filename], self.token_list))

  def testMatchUrlMissingStartToken(self):
    """Verify no match when token_list lacks beginning of filename."""
    self.token_list[0] = 'ghi'
    self.assertFalse(cb_url_lib.MatchUrl([self.filename], self.token_list))

  def testMatchUrlMissingEndToken(self):
    """Verify no match when token_list lacks end of filename."""
    self.token_list[1] = '.bi'
    self.assertFalse(cb_url_lib.MatchUrl([self.filename], self.token_list))


class TestDownload(mox.MoxTestBase):
  """Unit tests realted to Download."""

  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(urllib, 'urlopen')
    self.mox.StubOutWithMock(cb_url_lib, 'RunCommand')
    self.url = 'test_url'
    self.gsd_url = IMAGE_GSD_BUCKET + self.url
    self.named_file = tempfile.NamedTemporaryFile()
    self.test_file = tempfile.TemporaryFile()
    self.test_file.write('Some sample content for testing.')
    self.test_file.seek(0) # must rewind file handle for read
    # Stub out os.path AFTER creating temp files
    self.mox.StubOutWithMock(os.path, 'join')

  def testUrlGoodLocalFileOpenSucceeds(self):
    """Verify return value when page opens properly."""
    os.path.join(IsA(str), IsA(str)).AndReturn(self.named_file.name)
    urllib.urlopen('test_url').AndReturn(self.test_file)
    self.mox.ReplayAll()
    self.assertTrue(cb_url_lib.Download(self.url))

  def testUrlBad(self):
    """Verify clean return value when page does not open properly."""
    os.path.join(IsA(str), IsA(str)).AndReturn('')
    urllib.urlopen('test_url').AndRaise(IOError)
    self.mox.ReplayAll()
    expected = False
    actual = cb_url_lib.Download(self.url)
    self.assertEqual(expected, actual)

  def testLocalFileOpenFails(self):
    """Verify clean return value when local file fails to open."""
    os.path.join(IsA(str), IsA(str)).AndReturn('')
    urllib.urlopen('test_url').AndReturn(self.test_file)
    self.mox.ReplayAll()
    self.assertFalse(cb_url_lib.Download(self.url))

  def testGsdUrlGoodLocalFileOpenSucceeds(self):
    """Verify return value when GSD URL opens properly."""
    test_result = CommandResult()
    test_result.returncode = 0

    os.path.join(IsA(str), IsA(str)).AndReturn(self.named_file.name)
    cb_url_lib.RunCommand(
        ['gsutil', 'cp', self.gsd_url, self.named_file.name],
        redirect_stdout=True, redirect_stderr=True).AndReturn(test_result)
    self.mox.ReplayAll()
    self.assertTrue(cb_url_lib.Download(self.gsd_url))

  def testGsdUrlFileCopyFails(self):
    """Verify return value when gsutil copy fails."""
    test_result = CommandResult()
    test_result.returncode = -1

    os.path.join(IsA(str), IsA(str)).AndReturn(self.named_file.name)
    cb_url_lib.RunCommand(
        ['gsutil', 'cp', self.gsd_url, self.named_file.name],
        redirect_stdout=True, redirect_stderr=True).AndReturn(test_result)
    self.mox.ReplayAll()
    self.assertFalse(cb_url_lib.Download(self.gsd_url))


class TestDetermineThenDownloadCheckMd5(mox.MoxTestBase):
  """Unit tests related to DetermineThenDownloadCheckMd5."""

  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(cb_url_lib, 'DetermineUrl')
    self.url = 'url'
    self.pattern = ['pattern']
    self.path = 'path'
    self.desc = 'desc'

  def testUrlGood(self):
    """Verify return value when determining URL succeeds."""
    self.mox.StubOutWithMock(cb_url_lib, 'DownloadCheckMd5')
    cb_url_lib.DetermineUrl(self.url, self.pattern).AndReturn(self.url)
    cb_url_lib.DownloadCheckMd5(self.url,
                                self.path,
                                self.desc).AndReturn('name')
    self.mox.ReplayAll()
    expected = 'name'
    actual = cb_url_lib.DetermineThenDownloadCheckMd5(self.url,
                                                      self.pattern,
                                                      self.path,
                                                      self.desc)
    self.assertEqual(expected, actual)

  def testUrlBad(self):
    """Verify clean return value when determining URL fails."""
    cb_url_lib.DetermineUrl(self.url, self.pattern).AndReturn(None)
    self.mox.ReplayAll()
    self.assertRaises(cb_url_lib.NameResolutionError,
                      cb_url_lib.DetermineThenDownloadCheckMd5,
                      self.url,
                      self.pattern,
                      self.path,
                      self.desc)


class TestCheckResourceExistsWithMd5(mox.MoxTestBase):
  """Unit tests related to CheckResourceExistsWithMd5."""

  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(os.path, 'exists')
    self.filename = 'file'
    self.md5filename = 'file.md5'

  def testFileExistsMd5FileExistsMd5ChecksOut(self):
    """Verify return value when all is well."""
    self.mox.StubOutWithMock(cb_url_lib, 'CheckMd5')
    os.path.exists('file').AndReturn(True)
    os.path.exists('file.md5').AndReturn(True)
    cb_url_lib.CheckMd5('file', 'file.md5').AndReturn(True)
    self.mox.ReplayAll()
    self.assertTrue(cb_url_lib.CheckResourceExistsWithMd5(self.filename,
                                                          self.md5filename))

  def testFileDoesNotExist(self):
    """Verify return value when local file does not exist."""
    os.path.exists('file').AndReturn(False)
    self.mox.ReplayAll()
    self.assertFalse(cb_url_lib.CheckResourceExistsWithMd5(self.filename,
                                                           self.md5filename))

  def testMd5FileDoesNotExist(self):
    """Verify return value when nonexistent md5 file name is given."""
    os.path.exists('file').AndReturn(True)
    os.path.exists('file.md5').AndReturn(False)
    self.mox.ReplayAll()
    self.assertFalse(cb_url_lib.CheckResourceExistsWithMd5(self.filename,
                                                           self.md5filename))

  def testMd5DoesNotChecksOut(self):
    """Verify return value when MD5 checksum is bad."""
    self.mox.StubOutWithMock(cb_url_lib, 'CheckMd5')
    os.path.exists('file').AndReturn(True)
    os.path.exists('file.md5').AndReturn(True)
    cb_url_lib.CheckMd5('file', 'file.md5').AndReturn(False)
    self.mox.ReplayAll()
    self.assertFalse(cb_url_lib.CheckResourceExistsWithMd5(self.filename,
                                                           self.md5filename))


class TestDownloadCheckMd5(mox.MoxTestBase):
  """Unit tests related to DownloadCheckMd5."""

  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(cb_url_lib, 'CheckResourceExistsWithMd5')
    self.url = 'url/file'
    self.md5url = 'url/file.md5'
    self.path = 'path'
    self.desc = 'desc'
    self.name = 'path/file'
    self.md5name = 'path/file.md5'

  def testResourceExists(self):
    """Test behavior when resource exists with good MD5."""
    cb_url_lib.CheckResourceExistsWithMd5(self.name,
                                          self.md5name).AndReturn(True)
    self.mox.ReplayAll()
    expected = self.name
    actual = cb_url_lib.DownloadCheckMd5(self.url, self.path, self.desc)
    self.assertEqual(expected, actual)

  def testDownloadsCheckMd5Succeed(self):
    """Test behavior when fetch is entirely successful."""
    self.mox.StubOutWithMock(cb_url_lib, 'Download')
    self.mox.StubOutWithMock(cb_url_lib, 'CheckMd5')
    cb_url_lib.CheckResourceExistsWithMd5(self.name,
                                          self.md5name).AndReturn(False)
    cb_url_lib.Download(self.url).AndReturn(True)
    cb_url_lib.Download(self.md5url).AndReturn(True)
    cb_url_lib.CheckMd5(self.name, self.md5name).AndReturn(True)
    self.mox.ReplayAll()
    expected = self.name
    actual = cb_url_lib.DownloadCheckMd5(self.url, self.path, self.desc)
    self.assertEqual(expected, actual)

  def testFileDownloadFails(self):
    """Test behavior when file fetch fails."""
    self.mox.StubOutWithMock(cb_url_lib, 'Download')
    cb_url_lib.CheckResourceExistsWithMd5(self.name,
                                          self.md5name).AndReturn(False)
    cb_url_lib.Download(self.url).AndReturn(False)
    self.mox.ReplayAll()
    self.assertRaises(BundlingError,
                      cb_url_lib.DownloadCheckMd5,
                      self.url,
                      self.path,
                      self.desc)

  def testMd5FileDownloadFails(self):
    """Test behavior when MD5 file fetch fails."""
    self.mox.StubOutWithMock(cb_url_lib, 'Download')
    cb_url_lib.CheckResourceExistsWithMd5(self.name,
                                          self.md5name).AndReturn(False)
    cb_url_lib.Download(self.url).AndReturn(True)
    cb_url_lib.Download(self.md5url).AndReturn(False)
    self.mox.ReplayAll()
    self.assertRaises(BundlingError,
                      cb_url_lib.DownloadCheckMd5,
                      self.url,
                      self.path,
                      self.desc)

  def testMd5CheckFails(self):
    """Test behavior when MD5 check fails."""
    self.mox.StubOutWithMock(cb_url_lib, 'Download')
    self.mox.StubOutWithMock(cb_url_lib, 'CheckMd5')
    cb_url_lib.CheckResourceExistsWithMd5(self.name,
                                          self.md5name).AndReturn(False)
    cb_url_lib.Download(self.url).AndReturn(True)
    cb_url_lib.Download(self.md5url).AndReturn(True)
    cb_url_lib.CheckMd5(self.name, self.md5name).AndReturn(False)
    self.mox.ReplayAll()
    self.assertRaises(BundlingError,
                      cb_url_lib.DownloadCheckMd5,
                      self.url,
                      self.path,
                      self.desc)


class TestConvertHttpToGsUrl(unittest.TestCase):
  """Unit tests for _ConvertHttpToGsUrl method."""

  def testConvertHttpToGsUrl(self):
    expected = 'gs://chromeos-releases/stable-channel/x86-alex/0.12.433.269/*'
    http_url = ('https://sandbox.google.com/storage/chromeos-releases/'
                'stable-channel/x86-alex/0.12.433.269')
    actual = cb_url_lib._ConvertHttpToGsUrl(http_url)
    self.assertEqual(expected, actual)


if __name__ == "__main__":
  logging.basicConfig(level=logging.CRITICAL)
  unittest.main()
