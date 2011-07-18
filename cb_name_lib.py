#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module contains methods for image naming and bundle input parsing."""

import cb_constants
import os


def GetNameComponents(board, version_string, alt_naming):
  """Determine URL and version components of script input.

  Args:
    board: target board
    version_string: string with image version information
    alt_naming: try alternative build naming
      False - default naming scheme
      True - append '-rc' to board for index html page and links
  Returns:
    url, a string, the image index page URL
    num, a string, the image version number
    cha, a string, the image channel
    key, a string, part of the image signing key label
  """
  num, cha, key = version_string.split('/')
  cha = cha + '-channel'
  if alt_naming:
    url = os.path.join(cb_constants.PREFIX, cha, board + '-rc', num)
  else:
    url = os.path.join(cb_constants.PREFIX, cha, board, num)
  return (url, num, cha, key)


def GetReleaseName(board, release, alt_naming=False):
  """Determines release page URL and naming pattern of desired release image.

  Args:
    board: target board
    release: release candidate version, channel, and signing key
    alt_naming: try alternative build naming
        False - default naming scheme
        True - append '-rc' to board for index html page and links
  Returns:
    rel_url: a string, the release page URL
    rel_pat: a string, the naming pattern for the release image
  """
  (rel_url, rel_no, rel_ch, rel_key) = GetNameComponents(board,
                                                         release,
                                                         alt_naming)
  rel_pat = '_'.join(['chromeos', rel_no, board, 'ssd', rel_ch,
             rel_key + '.*[.]bin$'])
  return (rel_url, rel_pat)


def GetFactoryName(board, factory, alt_naming=False):
  """Determines release page URL and naming pattern of desired factory image.

  Args:
    board: target board
    factory: factory version and channel
    alt_naming: try alternative build naming
        False - default naming scheme
        True - append '-rc' to board for index html page and links
  Returns:
    fac_url: a string, the release page URL
    fac_pat: a string, the naming pattern for the factory image
  """
  fac_no, fac_ch = factory.split('/')
  fac_ch = fac_ch + '-channel'
  if alt_naming:
    fac_url = os.path.join(cb_constants.PREFIX, fac_ch, board + '-rc', fac_no)
  else:
    fac_url = os.path.join(cb_constants.PREFIX, fac_ch, board, fac_no)
  fac_pat = ''.join(['ChromeOS-factory-', fac_no, '.*', board, '[.]zip$'])
  return (fac_url, fac_pat)


def GetRecoveryName(board, recovery, alt_naming=False):
  """Determines release page URL and naming pattern of desired recovery image.

  Args:
    board: target board
    recovery: recovery version, channel, and signing key
    alt_naming: try alternative build naming
        False - default naming scheme
        True - append '-rc' to board for index html page and links
  Returns:
    rec_url: a string, the release page URL
    rec_pat: a string, the naming pattern for the recovery image
  """
  (rec_url, rec_no, rec_ch, rec_key) = GetNameComponents(board,
                                                         recovery,
                                                         alt_naming)
  rec_pat = '_'.join(['chromeos', rec_no, board, 'recovery', rec_ch,
             rec_key + '.*[.]bin$'])
  return (rec_url, rec_pat)
