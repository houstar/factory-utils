#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module is a generic library for factory bundle production."""

import cb_archive_hashing_lib
import cb_command_lib
import cb_constants
import cb_name_lib
import cb_url_lib
import logging
import os
import re
import shutil

from cb_command_lib import AskUserConfirmation
from cb_constants import BundlingError
from cb_url_lib import DetermineThenDownloadCheckMd5


def CheckBundleInputs(image_names, options):
  """Checks the input for making a factory bundle.

  In particular:
  - checks for conflicting input flags no_firmware and fsi
  - binary image names correctly passed by image fetch
  - binary image names point to existing files

  Assuming a second recovery image implies a second release image.

  Args:
    image_names: a dict, values are absolute file paths for keys:
      'ssd': release image
      'ssd2': second release image or None
      'recovery': recovery image
      'recovery2': second recovery image or None
      'factorybin': factory binary
    options: an object of input arguments to the script
      possible options include:
        fsi: a boolean, True when processing for a Final Shipping Image
        fw: a boolean, True when script should extract firmware
        release2: optional second release version, channel, and signing key
        recovery2: optional second recovery version, channel, and signing key
  Raises:
    BundlingError when a check fails.
  """
  if not options.fw and not options.fsi:
    raise BundlingError('Can only skip firmware extraction for '
                        'final shipping image.')
  ssd_name = image_names.get('ssd', None)
  rec_name = image_names.get('recovery', None)
  fac_name = image_names.get('factorybin', None)
  msg = []
  if ssd_name:
    if not os.path.isfile(ssd_name):
      msg.append('SSD image %s does not exist.' % ssd_name)
  else:
    msg.append('Bundling method needs ssd image name.')
  if rec_name:
    if not os.path.isfile(rec_name):
      msg.append('Recovery image %s does not exist.' % rec_name)
  else:
    msg.append('Bundling method needs recovery image name.')
  if fac_name:
    if not os.path.isfile(fac_name):
      msg.append('Factory image %s does not exist.' % fac_name)
  else:
    msg.append('Bundling method needs factory image name.')
  if options.recovery2:
    # we infer second release image should exist, since script options
    # might not list second release image, implying recovery to ssd conversion
    ssd_name2 = image_names.get('ssd2', None)
    if ssd_name2:
      if not os.path.isfile(ssd_name2):
        msg.append('Second SSD image %s does not exist.' % ssd_name2)
    else:
      msg.append('Bundling method needs second ssd image name.')
    rec_name2 = image_names.get('recovery2', None)
    if rec_name2:
      if not os.path.isfile(rec_name2):
        msg.append('Second recovery image %s does not exist.' % rec_name2)
    else:
      msg.append('Bundling method needs second recovery image name.')
  if msg:
    raise BundlingError('\n'.join(msg))


def MakeFactoryBundle(image_names, options):
  """Produces a factory bundle from the downloaded images.

  Requires current directory to be <ChromeOS_root>/src/scripts.
  Requires sudoer password entry to mount SSD image.
  Bundle is named with input version as well as the current date.
  Forces exit if any bundle components exist, use flags to override.
  Only extracts firmware from one release image.
  Assuming a second recovery image implies a second release image.

  Args:
    image_names: a dict, values are absolute file paths for keys:
      'ssd': release image or None
      'ssd2': second release image or None
      'recovery': recovery image
      'recovery2': second recovery image or None
      'factorybin': factory binary
    options: an object of input arguments to the script
      possible options include:
        fsi: a boolean, True when processing for a Final Shipping Image
        fw: a boolean, True when script should extract firmware
        version: key and version for bundle naming, e.g. mp9x
        bundle_dir: destination root directory for factory bundle files
        tar_dir: destination directory for factory bundle tar file
        force: a boolean, True when any existing bundle files can be deleted
  Returns:
    a string, the absolute path name of the factory bundle tar created
  Raises:
    BundlingError on bad input, inability to write, or firmware extract fail.
  """
  # TODO(benwin) refactor this method, it is getting long
  # shorten names
  fsi = options.fsi
  firmware = options.fw
  version = options.version
  mount_point = options.mount_point
  bundle_dir = options.bundle_dir
  tar_dir = options.tar_dir
  del_ok = options.force
  # throws BundlingError if needed resources do not exist or options conflict
  CheckBundleInputs(image_names, options)
  ssd_name = image_names.get('ssd', None)
  ssd_name2 = image_names.get('ssd2', None)
  rec_name = image_names.get('recovery', None)
  rec_name2 = image_names.get('recovery2', None)
  fac_name = image_names.get('factorybin', None)
  if bundle_dir:
    if not os.path.isdir(bundle_dir):
      raise BundlingError('Provided directory %s does not exist.' % bundle_dir)
    if not os.access(bundle_dir, os.W_OK):
      raise BundlingError('Provided directory %s not writable.' % bundle_dir)
  else:
    bundle_dir = os.path.join(cb_constants.WORKDIR,
                              cb_name_lib.GetBundleDefaultName(
                                version=version))
  if os.path.exists(bundle_dir):
    if del_ok:
      shutil.rmtree(bundle_dir)
    else:
      msg = 'Bundle directory %s already exists. Ok to overwrite?' % bundle_dir
      ans = AskUserConfirmation(msg)
      if ans:
        shutil.rmtree(bundle_dir)
      else:
        raise BundlingError('Directory %s exists. Use -f to overwrite.' %
                            bundle_dir)
  os.mkdir(bundle_dir)
  release_dir = os.path.join(bundle_dir, 'release')
  os.mkdir(release_dir)
  recovery_dir = os.path.join(bundle_dir, 'recovery')
  os.mkdir(recovery_dir)
  factory_dir = os.path.join(bundle_dir, 'factory')
  os.mkdir(factory_dir)
  if tar_dir:
    if not os.path.isdir(tar_dir):
      # input given but bad
      logging.warning('Provided directory %s does not exist, using %s',
                      tar_dir, cb_constants.WORKDIR)
      tar_dir = cb_constants.WORKDIR
  else:
    # make default have cleaner output
    tar_dir = cb_constants.WORKDIR
  if firmware:
    firmware_dest = os.path.join(bundle_dir, 'firmware')
    if os.path.exists(firmware_dest):
      if del_ok:
        shutil.rmtree(firmware_dest)
      else:
        msg = ('Bundle directory %s already exists. Ok to overwrite?' %
               firmware_dest)
      ans = AskUserConfirmation(msg)
      if ans:
        shutil.rmtree(firmware_dest)
      else:
        raise BundlingError('Directory %s exists. Use -f to overwrite.' %
                            firmware_dest)
    os.mkdir(firmware_dest)
    cb_command_lib.ExtractFirmware(ssd_name, firmware_dest, mount_point)
    logging.info('Successfully extracted firmware to %s', firmware_dest)
  shutil.copy(ssd_name, release_dir)
  shutil.copy(rec_name, recovery_dir)
  if options.release2:
    shutil.copy(ssd_name2, release_dir)
  if options.recovery2:
    if not options.release2:
      # converted from recovery, still need to copy file
      shutil.copy(ssd_name2, release_dir)
    shutil.copy(rec_name2, recovery_dir)
  if not fsi:
    # TODO(benwin) copy install shim into bundle_dir/shim
    shutil.copy(fac_name, factory_dir)
  MakeMd5Sums(bundle_dir)
  logging.info('Completed copying factory bundle files to %s', bundle_dir)
  logging.info('Tarring bundle files, this operation is resource-intensive.')
  tarname = cb_archive_hashing_lib.MakeTar(bundle_dir, tar_dir)
  if not tarname:
    raise BundlingError('Failed to create tar file of bundle directory.')
  logging.info('Completed creating factory bundle tar file in %s.',
               cb_constants.WORKDIR)
  abstarname = os.path.join(tar_dir, tarname)
  return abstarname


def MakeMd5Sums(bundle_dir):
  """Generate MD5 checksums for all binary components of factory bundle.

  Args:
    bundle_dir: absolute path to directory containing factory bundle files
  Raises:
    BundlingError on failure
  """
  file_list = []
  binary_file_pattern = re.compile('.*[.]bin$|.*[.]fd$')
  for directory in os.listdir(bundle_dir):
    for filename in os.listdir(os.path.join(bundle_dir, directory)):
      if re.search(binary_file_pattern, filename):
        file_list.append(os.path.join(bundle_dir, directory, filename))
  md5filename = os.path.join(bundle_dir, 'file_checksum.md5')
  try:
    with open(md5filename, 'w') as md5file:
      for absfilename in file_list:
        md5sum = cb_archive_hashing_lib.GenerateMd5(absfilename)
        if not md5sum:
          raise BundlingError('Failed to compute MD5 checksum for file %s.' %
                              absfilename)
        rel_name_list = ['.']
        rel_name_list.extend(absfilename.split(os.sep)[-2:])
        relfilename = os.sep.join(rel_name_list)
        md5file.write(md5sum + '  ' + relfilename + '\n')
  except IOError:
    raise BundlingError('Failed to compute md5 checksums for factory bundle.')


def FetchImages(options, alt_naming=0):
  """Fetches images for factory bundle specified by args input

  Args:
    options: an object containing inputs to the script
      possible options include:
        board: target board
        board2: optional second target board
        release: release candidate version, channel, and signing key
        release2: optional second release version, channel, and signing key
        factory: factory image version and channel
        recovery: recovery image version, channel, and signing key
        recovery2: optional second recovery version, channel, and signing key
        fsi: a boolean, True when processing for Final Shipping Image
        force: a boolean, True when any existing bundle files can be deleted
    alt_naming: optional try alternative build naming
        0 - default naming scheme
        1 - append '-rc' to board for index html page and links
        2 - remove chromeos-official for index html page and links
  Returns:
    a dict, values are absolute file paths for keys:
      'ssd': release image
      'ssd2': second release image or None
      'recovery': recovery image
      'recovery2': second recovery image or None
      'factorybin': factory binary
  Raises:
    BundlingError when resources cannot be fetched.
  """
  # shorten names
  board = options.board
  board2 = options.board2
  release = options.release
  release2 = options.release2
  factory = options.factory
  recovery = options.recovery
  recovery2 = options.recovery2
  fsi = options.fsi
  # TODO(benwin) refactor this function, it is too long
  if release:
    rel_url, rel_pat = cb_name_lib.GetReleaseName(board, release, alt_naming)
  fac_url, fac_pat = cb_name_lib.GetFactoryName(board, factory, alt_naming)
  rec_url, rec_pat = cb_name_lib.GetRecoveryName(board, recovery, alt_naming)
  # Release
  if release:
    rel_name = cb_url_lib.DetermineThenDownloadCheckMd5(rel_url,
                                             rel_pat,
                                             cb_constants.WORKDIR,
                                             'Release image')
  # Optional Extra Release
  if release2:
    rel_url2, rel_pat2 = cb_name_lib.GetReleaseName(board2,
                                                    release2,
                                                    alt_naming)
    rel_name2 = DetermineThenDownloadCheckMd5(rel_url2,
                                              rel_pat2,
                                              cb_constants.WORKDIR,
                                              'Second release image')
  else:
    rel_name2 = None
  # Recovery
  rec_name = cb_url_lib.DetermineThenDownloadCheckMd5(rec_url,
                                           rec_pat,
                                           cb_constants.WORKDIR,
                                           'Recovery image')
  # if needed, run recovery to ssd conversion now that we have recovery image
  if not release:
    rel_name = cb_command_lib.ConvertRecoveryToSsd(rec_name,
                                                   options.board,
                                                   options.recovery,
                                                   options.force)
    if not cb_archive_hashing_lib.MakeMd5(rel_name, rel_name + '.md5'):
      raise BundlingError('Failed to create md5 checksum for file %s.' %
                          rel_name)
  # Optional Extra Recovery
  if recovery2:
    rec_url2, rec_pat2 = cb_name_lib.GetRecoveryName(board2,
                                                     recovery2,
                                                     alt_naming)
    rec_name2 = DetermineThenDownloadCheckMd5(rec_url2,
                                              rec_pat2,
                                              cb_constants.WORKDIR,
                                              'Second recovery image')
  else:
    rec_name2 = None
  # if provided a second recovery image but no matching ssd, run conversion
  if recovery2 and not release2:
    rel_name2 = cb_command_lib.ConvertRecoveryToSsd(rec_name2,
                                                    options.board2,
                                                    options.recovery2,
                                                    options.force)
  # Factory
  if not fsi:
    fac_det_url = cb_url_lib.DetermineUrl(fac_url, fac_pat)
    if not fac_det_url:
      raise BundlingError('Factory image exact URL could not be determined '
                          'on page %s given pattern %s.' % (fac_url, fac_pat))
    fac_name = os.path.join(cb_constants.WORKDIR, fac_det_url.split('/')[-1])
    if os.path.exists(fac_name):
      logging.info('Resource %s already exists, skipping fetch.',
                   fac_name)
    else:
      logging.info('Downloading ' + fac_det_url)
      if not cb_url_lib.Download(fac_det_url):
        raise BundlingError('Factory image could not be fetched.')
    factorybin = os.path.join('factory_test', 'chromiumos_factory_image.bin')
    absfactorybin = os.path.join(cb_constants.WORKDIR, factorybin)
    if os.path.exists(absfactorybin):
      logging.info('Resource %s already present, skipping zip extraction.',
                   absfactorybin)
    else:
      logging.info('Extracting factory image binary')
      if not cb_archive_hashing_lib.ZipExtract(fac_name,
                                               factorybin,
                                               path=cb_constants.WORKDIR):
        raise BundlingError('Could not find chromiumos_factory_image.bin '
                            'in factory image.')
  # TODO(benwin) add naming, download, and check for factory install shim
  image_names = dict(ssd=rel_name,
                     ssd2=rel_name2,
                     recovery=rec_name,
                     recovery2=rec_name2,
                     factorybin=absfactorybin)
  return image_names


def CheckParseOptions(options, parser):
  """Checks parse options input to the factory bundle script.

  Args:
    options: an object with the input options to the script
    parser: the OptionParser used to parse the input options
  Raises:
    BundlingError when parse options are bad
  """
  # TODO(benwin) check that clean does not occur with any other options
  if not options.clean and not options.factory:
    parser.print_help()
    raise BundlingError('\nMust specify factory zip version/channel.')
