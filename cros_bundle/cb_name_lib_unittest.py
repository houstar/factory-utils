#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for the cb_name_lib module."""

import mox
import sys
import unittest

from cb_constants import IMAGE_GSD_PREFIX, IMAGE_SERVER_PREFIX
import cb_name_lib


class TestGetNameComponents(unittest.TestCase):
  """Tests related to GetNameComponents."""

  def setUp(self):
    self.board = 'x86-alex'
    self.version_string = '0.12.433.269/stable/mp'

  def testUseDefaultNaming(self):
    """Verify correct string tuple returned using default naming scheme."""
    expected = (IMAGE_SERVER_PREFIX + '/stable-channel/x86-alex/0.12.433.269',
                '0.12.433.269', 'stable-channel', 'mp')
    actual = cb_name_lib.GetNameComponents(self.board, self.version_string, 0)
    self.assertEqual(expected, actual)

  def testUseAltNamingOne(self):
    """Verify correct string tuple returned using alt_naming scheme 1."""
    expected = (IMAGE_SERVER_PREFIX + '/stable-channel/x86-alex-rc/' +
                '0.12.433.269', '0.12.433.269', 'stable-channel', 'mp')
    actual = cb_name_lib.GetNameComponents(self.board, self.version_string, 1)
    self.assertEqual(expected, actual)

  def testUseAltNamingTwo(self):
    """Verify correct string tuple returned using alt_naming scheme 2."""
    mod_prefix = '/'.join(IMAGE_SERVER_PREFIX.split('/')[:-1])
    expected = (mod_prefix + '/stable-channel/x86-alex/0.12.433.269',
                '0.12.433.269', 'stable-channel', 'mp')
    actual = cb_name_lib.GetNameComponents(self.board, self.version_string, 2)
    self.assertEqual(expected, actual)

  def testUseAltNamingThree(self):
    """Verify correct string tuple returned using alt_naming scheme 3."""
    expected = (IMAGE_GSD_PREFIX + '/stable-channel/x86-alex/0.12.433.269',
                '0.12.433.269', 'stable-channel', 'mp')
    actual = cb_name_lib.GetNameComponents(self.board, self.version_string, 3)
    self.assertEqual(expected, actual)


class TestGetReleaseName(unittest.TestCase):
  """Tests related to GetReleaseName."""

  def setUp(self):
    self.board = 'x86-alex'
    self.version_string = '0.12.433.269/stable/mp'

  def testReleaseUseDefaultNaming(self):
    """Verify correct string tuple returned using default naming scheme."""
    expected = (IMAGE_SERVER_PREFIX + '/stable-channel/x86-alex/0.12.433.269',
                ['chromeos', '0.12.433.269', 'x86-alex', 'ssd',
                 'stable-channel', 'mp', '.bin'])
    actual = cb_name_lib.GetReleaseName(self.board,
                                        self.version_string,
                                        0)
    self.assertEqual(expected, actual)

  def testReleaseUseAlternativeNaming(self):
    """Verify correct string tuple returned using alternative naming scheme."""
    expected = (IMAGE_SERVER_PREFIX + '/stable-channel/x86-alex-rc/' +
                '0.12.433.269',
                ['chromeos', '0.12.433.269', 'x86-alex', 'ssd',
                 'stable-channel', 'mp', '.bin'])
    actual = cb_name_lib.GetReleaseName(self.board,
                                        self.version_string,
                                        1)
    self.assertEqual(expected, actual)


class TestGetFactoryName(unittest.TestCase):
  """Tests related to GetFactoryName."""

  def setUp(self):
    self.board = 'x86-alex'
    self.version_string = '0.12.433.269/stable'

  def testFactoryUseDefaultNaming(self):
    """Verify correct string tuple returned using default naming scheme."""
    expected = (IMAGE_SERVER_PREFIX + '/stable-channel/x86-alex/0.12.433.269',
                ['chromeos-factory', '0.12.433.269', 'x86-alex', '.zip'])
    actual = cb_name_lib.GetFactoryName(self.board, self.version_string, 0)
    self.assertEqual(expected, actual)

  def testFactoryUseAlternativeNamingOne(self):
    """Verify correct string tuple returned using alt_naming scheme 1."""
    expected = (IMAGE_SERVER_PREFIX + '/stable-channel/x86-alex-rc/' +
                '0.12.433.269',
                ['chromeos-factory', '0.12.433.269', 'x86-alex', '.zip'])
    actual = cb_name_lib.GetFactoryName(self.board, self.version_string, 1)
    self.assertEqual(expected, actual)

  def testFactoryUseAlternativeNamingTwo(self):
    """Verify correct string tuple returned using alt_naming scheme 2."""
    mod_prefix = '/'.join(IMAGE_SERVER_PREFIX.split('/')[:-1])
    expected = (mod_prefix + '/stable-channel/x86-alex/0.12.433.269',
                ['chromeos-factory', '0.12.433.269', 'x86-alex', '.zip'])
    actual = cb_name_lib.GetFactoryName(self.board, self.version_string, 2)
    self.assertEqual(expected, actual)

  def testFactoryUseAlternativeNamingThree(self):
    """Verify correct string tuple returned using alt_naming scheme 3."""
    expected = (IMAGE_GSD_PREFIX + '/stable-channel/x86-alex/0.12.433.269',
                ['chromeos-factory', '0.12.433.269', 'x86-alex', '.zip'])
    actual = cb_name_lib.GetFactoryName(self.board, self.version_string, 3)
    self.assertEqual(expected, actual)


class TestGetRecoveryName(unittest.TestCase):
  """Tests related to GetRecoveryName."""

  def setUp(self):
    self.board = 'x86-alex'
    self.version_string = '0.12.433.269/stable/mp'

  def testRecoveryUseDefaultNaming(self):
    """Verify correct string tuple returned using default naming scheme."""
    expected = (IMAGE_SERVER_PREFIX + '/stable-channel/x86-alex/0.12.433.269',
                ['chromeos', '0.12.433.269', 'x86-alex', 'recovery',
                 'stable-channel', 'mp', '.bin'])
    actual = cb_name_lib.GetRecoveryName(self.board,
                                         self.version_string,
                                         0)
    self.assertEqual(expected, actual)

  def testRecoveryUseAlternativeNaming(self):
    """Verify correct string tuple returned using alternative naming scheme."""
    expected = (IMAGE_SERVER_PREFIX + '/stable-channel/x86-alex-rc/' +
                '0.12.433.269',
                ['chromeos', '0.12.433.269', 'x86-alex', 'recovery',
                 'stable-channel', 'mp', '.bin'])
    actual = cb_name_lib.GetRecoveryName(self.board,
                                         self.version_string,
                                         1)
    self.assertEqual(expected, actual)


class TestResolveRecoveryUrl(mox.MoxTestBase):
  """Unit tests related to ResolveRecoveryUrl."""

  def setUp(self):
    self.mox = mox.Mox()
    self.image_name = '/abs/path/to/image_name'
    self.board = 'board-name'
    self.recovery = 'rec_no/rec_channel/rec_key'
    self.index_page = 'index_page'
    self.rec_pat = 'recovery_image_name_pattern'
    self.rec_url = 'recovery_image_url'
    self.mox.StubOutWithMock(cb_name_lib, 'GetRecoveryName')
    self.mox.StubOutWithMock(cb_name_lib, 'DetermineUrl')

  def testDefaultNamingSucceeds(self):
    """Verify return value when default naming resolution works."""
    cb_name_lib.GetRecoveryName(self.board, self.recovery, 0).AndReturn(
        (self.index_page, self.rec_pat))
    cb_name_lib.DetermineUrl(self.index_page, self.rec_pat).AndReturn(
        self.rec_url)
    self.mox.ReplayAll()
    expected = (self.rec_url, self.index_page)
    actual = cb_name_lib.ResolveRecoveryUrl(self.board, self.recovery)
    self.assertEqual(expected, actual)

  def testAlternativeNamingSucceeds(self):
    """Verify return value when alternative naming resolution works."""
    cb_name_lib.GetRecoveryName(self.board,
                                self.recovery,
                                1).AndReturn((self.index_page, self.rec_pat))
    cb_name_lib.DetermineUrl(self.index_page,
                             self.rec_pat).AndReturn(self.rec_url)
    self.mox.ReplayAll()
    expected = (self.rec_url, self.index_page)
    actual = cb_name_lib.ResolveRecoveryUrl(self.board, self.recovery,
                                            alt_naming=1)
    self.assertEqual(expected, actual)


if __name__ == '__main__':
  unittest.main()
