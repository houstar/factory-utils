#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for the cb_name_lib module."""

import sys
import unittest

import cb_constants
import cb_name_lib


class TestGetNameComponents(unittest.TestCase):
  """Tests related to GetNameComponents."""

  def setUp(self):
    self.board = 'x86-alex'
    self.version_string = '0.12.433.269/stable/mp'

  def testUseDefaultNaming(self):
    """Verify correct string tuple returned using default naming scheme."""
    alt_naming = False
    expected = (cb_constants.PREFIX + '/stable-channel/x86-alex/0.12.433.269',
                '0.12.433.269',
                'stable-channel',
                'mp')
    actual = cb_name_lib.GetNameComponents(self.board,
                                           self.version_string,
                                           alt_naming)
    self.assertEqual(expected, actual)

  def testUseAltNaming(self):
    """Verify correct string tuple returned using alternative naming scheme."""
    alt_naming = True
    expected = (cb_constants.PREFIX + '/stable-channel/x86-alex-rc/' +
                '0.12.433.269',
                '0.12.433.269',
                'stable-channel',
                'mp')
    actual = cb_name_lib.GetNameComponents(self.board,
                                           self.version_string,
                                           alt_naming)
    self.assertEqual(expected, actual)


class TestGetReleaseName(unittest.TestCase):
  """Tests related to GetReleaseName."""

  def setUp(self):
    self.board = 'x86-alex'
    self.version_string = '0.12.433.269/stable/mp'

  def testReleaseUseDefaultNaming(self):
    """Verify correct string tuple returned using default naming scheme."""
    alt_naming = False
    expected = (cb_constants.PREFIX + '/stable-channel/x86-alex/0.12.433.269',
                'chromeos_0.12.433.269_x86-alex_ssd_stable-channel_' +
                'mp.*[.]bin$')
    actual = cb_name_lib.GetReleaseName(self.board,
                                        self.version_string,
                                        alt_naming)
    self.assertEqual(expected, actual)

  def testReleaseUseAlternativeNaming(self):
    """Verify correct string tuple returned using alternative naming scheme."""
    alt_naming = True
    expected = (cb_constants.PREFIX + '/stable-channel/x86-alex-rc/' +
                '0.12.433.269',
                'chromeos_0.12.433.269_x86-alex_ssd_stable-channel_' +
                'mp.*[.]bin$')
    actual = cb_name_lib.GetReleaseName(self.board,
                                        self.version_string,
                                        alt_naming)
    self.assertEqual(expected, actual)


class TestGetFactoryName(unittest.TestCase):
  """Tests related to GetFactoryName."""

  def setUp(self):
    self.board = 'x86-alex'
    self.version_string = '0.12.433.269/stable'

  def testFactoryUseDefaultNaming(self):
    """Verify correct string tuple returned using default naming scheme."""
    alt_naming = False
    expected = (cb_constants.PREFIX + '/stable-channel/x86-alex/0.12.433.269',
                'ChromeOS-factory-0.12.433.269.*x86-alex[.]zip$')
    actual = cb_name_lib.GetFactoryName(self.board,
                                        self.version_string,
                                        alt_naming)
    self.assertEqual(expected, actual)

  def testFactoryUseAlternativeNaming(self):
    """Verify correct string tuple returned using alternative naming scheme."""
    alt_naming = True
    expected = (cb_constants.PREFIX + '/stable-channel/x86-alex-rc/' +
                '0.12.433.269',
                'ChromeOS-factory-0.12.433.269.*x86-alex[.]zip$')
    actual = cb_name_lib.GetFactoryName(self.board,
                                        self.version_string,
                                        alt_naming)
    self.assertEqual(expected, actual)


class TestGetRecoveryName(unittest.TestCase):
  """Tests related to GetRecoveryName."""

  def setUp(self):
    self.board = 'x86-alex'
    self.version_string = '0.12.433.269/stable/mp'

  def testRecoveryUseDefaultNaming(self):
    """Verify correct string tuple returned using default naming scheme."""
    alt_naming = False
    expected = (cb_constants.PREFIX + '/stable-channel/x86-alex/0.12.433.269',
                'chromeos_0.12.433.269_x86-alex_recovery_stable-channel_' +
                'mp.*[.]bin$')
    actual = cb_name_lib.GetRecoveryName(self.board,
                                        self.version_string,
                                        alt_naming)
    self.assertEqual(expected, actual)

  def testRecoveryUseAlternativeNaming(self):
    """Verify correct string tuple returned using alternative naming scheme."""
    alt_naming = True
    expected = (cb_constants.PREFIX + '/stable-channel/x86-alex-rc/' +
                '0.12.433.269',
                'chromeos_0.12.433.269_x86-alex_recovery_stable-channel_' +
                'mp.*[.]bin$')
    actual = cb_name_lib.GetRecoveryName(self.board,
                                        self.version_string,
                                        alt_naming)
    self.assertEqual(expected, actual)


if __name__ == '__main__':
  unittest.main()

