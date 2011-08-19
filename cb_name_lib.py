#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module contains methods for image naming and bundle input parsing."""

import datetime
import logging
import os

import cb_constants
import cb_url_lib

from cb_constants import BundlingError
from cb_url_lib import NameResolutionError

NUM_NAMING_SCHEMES = 3
DATE_FORMAT = '%Y_%m_%d'


def GetBundleDefaultName(version=None):
  """Generates factory bundle default name.

  Args:
    version: optional key and version for bundle naming, e.g. mp9x
  Returns:
    a string, the default name of the factory bundle
  """
  today = datetime.date.today().strftime(DATE_FORMAT)
  items = ['factory', 'bundle', today]
  if version:
    items.insert(2, version)
  return '_'.join(items)


def GetNameComponents(board, version_string, alt_naming):
  """Determine URL and version components of script input.

  Args:
    board: target board
    version_string: string with image version information
    alt_naming: try alternative build naming
      0 - default naming scheme
      1 - append '-rc' to board for index html page and links
      2 - remove chromeos-official for index html page and links
  Returns:
    url, a string, the image index page URL
    num, a string, the image version number
    cha, a string, the image channel
    key, a string, part of the image signing key label
  """
  num, cha, key = version_string.split('/')
  cha = cha + '-channel'
  if alt_naming == 1:
    url = os.path.join(cb_constants.PREFIX, cha, board + '-rc', num)
  elif alt_naming == 2:
    url = os.path.join(cb_constants.PREFIX.replace('chromeos-official', ''),
                       cha, board, num)
  else:
    url = os.path.join(cb_constants.PREFIX, cha, board, num)
  return (url, num, cha, key)


def GetReleaseName(board, release, alt_naming=0):
  """Determines release page URL and naming pattern of desired release image.

  Args:
    board: target board
    release: release candidate version, channel, and signing key
    alt_naming: optional try alternative build naming
      0 - default naming scheme
      1 - append '-rc' to board for index html page and links
      2 - remove chromeos-official for index html page and links
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


def GetFactoryName(board, factory, alt_naming=0):
  """Determines release page URL and naming pattern of desired factory image.

  Args:
    board: target board
    factory: factory version and channel
    alt_naming: optional try alternative build naming
      0 - default naming scheme
      1 - append '-rc' to board for index html page and links
      2 - remove chromeos-official for index html page and links
  Returns:
    fac_url: a string, the release page URL
    fac_pat: a string, the naming pattern for the factory image
  """
  fac_no, fac_ch = factory.split('/')
  fac_ch = fac_ch + '-channel'
  if alt_naming == 1:
    fac_url = os.path.join(cb_constants.PREFIX, fac_ch, board + '-rc', fac_no)
  elif alt_naming == 2:
    fac_url = os.path.join(cb_constants.PREFIX.replace(
                           'chromeos-official', ''),
                           fac_ch,
                           board,
                           fac_no)
  else:
    fac_url = os.path.join(cb_constants.PREFIX, fac_ch, board, fac_no)
  fac_pat = ''.join(['ChromeOS-factory-', fac_no, '.*', board, '[.]zip$'])
  return (fac_url, fac_pat)


def GetShimName(board, shim, alt_naming=0):
  """Determines release page URL and naming pattern of desired install shim.

  Args:
    board: target board
    shim: factory install shim version, channel, and signing key
    alt_naming: optional try alternative build naming
      0 - default naming scheme
      1 - append '-rc' to board for index html page and links
      2 - remove chromeos-official for index html page and links
  Returns:
    rec_url: a string, the release page URL
    rec_pat: a string, the naming pattern for the install shim
  """
  (shim_url, shim_no, shim_ch, shim_key) = GetNameComponents(board,
                                                             shim,
                                                             alt_naming)
  shim_pat = '_'.join(['chromeos', shim_no, board, 'factory', shim_ch,
             shim_key + '.*[.]bin$'])
  return (shim_url, shim_pat)


def GetRecoveryName(board, recovery, alt_naming=0):
  """Determines release page URL and naming pattern of desired recovery image.

  Args:
    board: target board
    recovery: recovery version, channel, and signing key
    alt_naming: optional try alternative build naming
      0 - default naming scheme
      1 - append '-rc' to board for index html page and links
      2 - remove chromeos-official for index html page and links
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


def ResolveRecoveryUrl(image_name, board, recovery, alt_naming=0):
  """Resolve URL for a recovery image.

  Args:
    image_name: absolute path name of recovery image to convert
    board: board name of recovery image to convert
    recovery: a string containing recovery image version/channel/signing_key
    alt_naming: optional try alternative build naming
      0 - default naming scheme
      1 - append '-rc' to board for index html page and links
      2 - remove chromeos-official for index html page and links
  Returns:
    a tuple containing:
      a string, the resolved URL
      a string, the html page where a link to the resolved URL is found
  Raises:
    NameResolutionError on failure
  """
  (index_page, rec_pat) = GetRecoveryName(board, recovery, alt_naming)
  rec_url = cb_url_lib.DetermineUrl(index_page, rec_pat)
  # TODO(benwin) common logic with DetermineThenDownloadCheckMd5, refactor?
  if not rec_url:
    raise NameResolutionError('Recovery image exact URL could not be '
                              'determined for version %s.' % recovery)
  return (rec_url, index_page)


def RunWithNamingRetries(default, funcname, *args):
  """Executes a function with arguments on various URL naming schemes.

  Assumes function provided accepts alt_naming as final parameter.
  Assumes function provided raises NameResolutionError to trigger retry.

  Args:
    default: return value on failure
    funcname: name of function to run
    *args: arbitrarily many arguments to provide to the function
  Returns:
    result of the first successful function call or default return on failure
  """
  alt_naming = 0
  while(alt_naming < NUM_NAMING_SCHEMES):
    try:
      logging.info('Trying function %s with naming scheme %d' %
                   (funcname.__name__, alt_naming))
      return funcname(*args, alt_naming=alt_naming)
    except NameResolutionError:
      logging.info('Tried naming scheme %d; trying alternative naming scheme' %
                   alt_naming)
      alt_naming = alt_naming + 1
  return default
