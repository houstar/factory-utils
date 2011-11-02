#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module is a generic library for factory bundle production."""

import logging
import os
import re
import shutil

from cb_archive_hashing_lib import MakeTar, GenerateMd5, MakeMd5, ZipExtract
from cb_command_lib import AskUserConfirmation, ExtractFirmware, \
    ConvertRecoveryToSsd
from cb_constants import BundlingError, WORKDIR
from cb_name_lib import GetBundleDefaultName, GetReleaseName, GetRecoveryName, \
    GetReleaseName, GetShimName, GetFactoryName
from cb_url_lib import DetermineThenDownloadCheckMd5, DetermineUrl, Download
from cb_util import RunCommand


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
      'shim': factory install shim
    options: an object of input arguments to the script
      possible options are:
        board: target board
        board2: optional second target board
        bundle_dir: destination root directory for factory bundle files
        chromeos_root: user-provided root of ChromeOS source tree checkout
        factory: factory image version/channel
        force: a boolean, True when all existing bundle files can be deleted
        fsi: a boolean, True when processing for a Final Shipping Image
        full_ssd: a boolean, True to make release image with stateful partition
        fw: a boolean, True when script should extract firmware
        recovery: recovery image version/channel/signing_key
        recovery2: optional second recovery version/channel/signing_key
        release: release candidate version/channel/signing_key
        release2: optional second release version/channel/signing_key
        tar_dir: destination directory for factory bundle tar file
        version: key and version for bundle naming, e.g. mp9x
  Raises:
    BundlingError when a check fails.
  """
  if not options.fw and not options.fsi:
    raise BundlingError('Can only skip firmware extraction for '
                        'final shipping image.')
  ssd_name = image_names.get('ssd', None)
  rec_name = image_names.get('recovery', None)
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
  if not options.fsi:
    fac_name = image_names.get('factorybin', None)
    shim_name = image_names.get('shim', None)
    if fac_name:
      if not os.path.isfile(fac_name):
        msg.append('Factory image %s does not exist.' % fac_name)
    else:
      msg.append('Bundling method needs factory image name.')
    if shim_name:
      if not os.path.isfile(shim_name):
        msg.append('Factory install shim %s does not exist.' % shim_name)
    else:
      msg.append('Bundling method needs factory install shim name.')
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
      'shim': signed factory install shim
    options: an object of input arguments to the script
      please see CheckBundleInputs above for possibilities
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
  shim_name = image_names.get('shim', None)
  if bundle_dir:
    if not os.path.isdir(bundle_dir):
      raise BundlingError('Provided directory %s does not exist.' % bundle_dir)
    if not os.access(bundle_dir, os.W_OK):
      raise BundlingError('Provided directory %s not writable.' % bundle_dir)
  else:
    bundle_dir = os.path.join(
        WORKDIR, GetBundleDefaultName(version=version))
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
  if not fsi:
    dir_list = ['release', 'recovery', 'factory', 'shim']
  else:
    dir_list = ['release', 'recovery']
  dir_dict = {}
  for dir_name in dir_list:
    directory = os.path.join(bundle_dir, dir_name)
    dir_dict[dir_name] = directory
    os.mkdir(directory)
  if tar_dir:
    if not os.path.isdir(tar_dir):
      # input given but bad
      logging.warning('Provided directory %s does not exist, using %s',
                      tar_dir, WORKDIR)
      tar_dir = WORKDIR
  else:
    # make default have cleaner output
    tar_dir = WORKDIR
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
    ExtractFirmware(ssd_name, firmware_dest, mount_point, options.board)
    logging.info('Successfully extracted firmware to %s', firmware_dest)
  shutil.copy(ssd_name, dir_dict.get('release', None))
  shutil.copy(rec_name, dir_dict.get('recovery', None))
  if options.release2:
    shutil.copy(ssd_name2, dir_dict.get('release', None))
  if options.recovery2:
    if not options.release2:
      # converted from recovery, still need to copy file
      shutil.copy(ssd_name2, dir_dict.get('release', None))
    shutil.copy(rec_name2, dir_dict.get('recovery', None))
  if not fsi:
    shutil.copy(shim_name, dir_dict.get('shim', None))
    shutil.copy(fac_name, dir_dict.get('factory', None))
  MakeMd5Sums(bundle_dir)
  logging.info('Completed copying factory bundle files to %s', bundle_dir)
  logging.info('Tarring bundle files, this operation is resource-intensive.')
  tarname = MakeTar(bundle_dir, tar_dir)
  if not tarname:
    raise BundlingError('Failed to create tar file of bundle directory.')
  logging.info('Completed creating factory bundle tar file in %s.', WORKDIR)
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

  lines_written = []
  try:
    with open(md5filename, 'w') as md5file:
      for absfilename in file_list:
        md5sum = GenerateMd5(absfilename)
        if not md5sum:
          raise BundlingError('Failed to compute MD5 checksum for file %s.' %
                              absfilename)
        rel_name_list = ['.']
        rel_name_list.extend(absfilename.split('/')[-2:])
        relfilename = '/'.join(rel_name_list)
        line = (md5sum + '  ' + relfilename + '\n')
        lines_written.append(line)
        md5file.write(line)
    return lines_written
  except IOError:
    raise BundlingError('Failed to open file for writing md5 checksums.')


def _GetResourceUrlAndPath(desc, get_func, *args):
  """Wrapper method for obtaining a resource.

  Args:
    desc: a string, resource description.
    get_func: a function object, function to execute.
    args: arguments to pass into func.

  Returns:
    url: a string, URL to the resource.
    path: a string, local path to the downloaded resource. Or None if error.
  """
  url, pat = get_func(*args)
  path = DetermineThenDownloadCheckMd5(url, pat, WORKDIR, desc)
  return (url, path)


def _HandleFactoryImageAndShim(options, alt_naming):
  """Logic for handling factory image and shim.

  Args:
    options: an object containing inputs to the script
    alt_naming: optional, see docstring for GetNameComponents in cb_name_lib.py

  Returns:
    absfactorybin: a string, path to factory image.
    shim_name: a string, name of factory shim.
  """
  fac_url, token_list = GetFactoryName(options.board, options.factory,
                                       alt_naming)
  fac_det_url = DetermineUrl(fac_url, token_list)
  if not fac_det_url:
    raise BundlingError('Factory image exact URL could not be determined '
                        'on page %s given pattern %s.' % (fac_url, token_list))

  fac_name = os.path.join(WORKDIR, os.path.basename(fac_det_url))
  if not os.path.exists(fac_name):
    logging.info('Downloading ' + fac_det_url)
    if not Download(fac_det_url):
      raise BundlingError('Factory image could not be fetched.')
  logging.info('Resource %s is present.', fac_name)

  factorybin = os.path.join('factory_test', 'chromiumos_factory_image.bin')
  absfactorybin = os.path.join(WORKDIR, factorybin)
  if not os.path.exists(absfactorybin):
    logging.info('Extracting factory image binary')
    if not ZipExtract(fac_name, factorybin, path=WORKDIR):
      raise BundlingError('Could not find chromiumos_factory_image.bin '
                          'in factory image.')
  logging.info('Resource %s is present.', absfactorybin)

  # Factory Install Shim
  _, token_list = GetShimName(options.board, options.shim, alt_naming)
  # shim is to be found on index page of recovery image sought, even if it
  # has a name that suggests it would be on another channel index page
  shim_name = DetermineThenDownloadCheckMd5(fac_url, token_list, WORKDIR,
                                            'Factory Install Shim')
  return (absfactorybin, shim_name)


def FetchImages(options, alt_naming=0):
  """Fetches images for factory bundle specified by args input

  Assuming second recovery implies second ssd should be made through conversion
  Assuming install shim surfaced on index page for first recovery image
  Default ssd conversion requires chroot setup and that this method be used
    in current directory <ChromeOS_root>/src/scripts

  Args:
    options: an object containing inputs to the script
      please see CheckBundleInputs above for possibilities
    alt_naming: optional, see docstring for GetNameComponents in cb_name_lib.py
  Returns:
    a dict, possible values are absolute file paths for keys:
      'ssd': release image
      'ssd2': second release image or None
      'recovery': recovery image
      'recovery2': second recovery image or None
      'factorybin': factory binary
      'shim': signed factory install shim
  Raises:
    BundlingError when resources cannot be fetched.
  """
  # Recovery
  rec_url, rec_name = _GetResourceUrlAndPath(
      'Recovery image', GetRecoveryName, options.board, options.recovery,
      alt_naming)

  # Release
  if options.release:
    rel_url, rel_name = _GetResourceUrlAndPath(
        'Release image', GetReleaseName, options.board, options.release,
        alt_naming)
  else:
    # if needed, run recovery to ssd conversion now that we have recovery image
    rel_name = ConvertRecoveryToSsd(rec_name, options)
    if not MakeMd5(rel_name, rel_name + '.md5'):
      raise BundlingError('Failed to create md5 checksum for %s' % rel_name)

  # Optional Extra Release
  rel_name2 = None
  if options.release2:
    rel_url2, rel_name2 = _GetResourceUrlAndPath(
        'Second release image', GetReleaseName, options.board2,
        options.release2, alt_naming)

  # Optional Extra Recovery
  rec_name2 = None
  if options.recovery2:
    rec_url2, rec_name2 = _GetResourceUrlAndPath(
        'Second recovery image', GetRecoveryName, options.board2,
        options.recovery2, alt_naming)
    # if provided a second recovery image but no matching ssd, run conversion
    if not options.release2:
      rel_name2 = ConvertRecoveryToSsd(rec_name2, options)

  image_names = dict(ssd=rel_name, ssd2=rel_name2, recovery=rec_name,
                     recovery2=rec_name2)
  # Factory and Shim
  if not options.fsi:
    (absfactorybin, shim_name) = _HandleFactoryImageAndShim(options, alt_naming)
    image_names.update(dict(factorybin=absfactorybin, shim=shim_name))

  return image_names


def CheckParseOptions(options, parser):
  """Checks parse options input to the factory bundle script.

  Args:
    options: an object with the input options to the script
      please see CheckBundleInputs above for possibilities
    parser: the OptionParser used to parse the input options
  Raises:
    BundlingError when parse options are bad
  """
  # TODO(benwin) check that clean does not occur with any other options
  if not options.clean and not options.factory:
    parser.print_help()
    raise BundlingError('\nMust specify factory zip version/channel.')
  if options.force:
    logging.info('Detected --force option, obtaining sudo privilege now.')
    logging.info('Remove --force option to list and confirm each command.')
    RunCommand(['sudo', '-v'])
  if not options.fsi and not options.shim:
    raise BundlingError('\nMust specify install shim for non-fsi bundle.')
