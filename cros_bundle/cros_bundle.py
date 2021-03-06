#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This script repackages ChromeOS images into a factory bundle.

Usage details in <ChromeOS_root>/src/platform/factory-utils/cros_bundle_readme.
"""

import logging
import os
import shutil

from cb_command_lib import IsInsideChroot, UploadToGsd
from cb_constants import BundlingError, MOUNT_POINT, WORKDIR
from cb_name_lib import RunWithNamingRetries
from cros_bundle_lib import CheckParseOptions, FetchImages, MakeFactoryBundle
from optparse import OptionParser


def CreateParser():
  """Creates a command-line flags parser for testing."""
  parser = OptionParser(usage=__doc__)
  parser.add_option('-b', '--board', action='store', type='string',
                    dest='board', help='target board')
  parser.add_option('-r', '--release', action='store', type='string',
                    dest='release', help='release candidate version')
  parser.add_option('--factory', action='store', type='string',
                    dest='factory', help='factory image version')
  parser.add_option('-s', '--shim', action='store', type='string',
                    dest='shim', help='install shim version')
  parser.add_option('--recovery', action='store', type='string',
                    dest='recovery', help='recovery image version')
  parser.add_option('--fsi', action='store_true', dest='fsi',
                    help='use to process for final shipping image')
  parser.add_option('--no_firmware', action='store_false', dest='fw',
                    default=True,
                    help='use to skip firmware extraction for fsi')
  parser.add_option('--version', action='store', type='string', dest='version',
                    help='release version number for bundle naming, e.g. mp9x')
  parser.add_option('--mountpt', action='store', dest='mount_point',
                    help='specify mount point for SSD image')
  parser.add_option('-f', '--force', action='store_true', dest='force',
                    default=False,
                    help='force overwrite of any existing bundle files')
  parser.add_option('--clean', action='store_true', dest='clean',
                    default=False,
                    help='remove all stored bundles files in tmp storage')
  parser.add_option('--bundle_dir', action='store', dest='bundle_dir',
                    help='absolute directory path for factory bundle files' +
                         ', ending is name for factory bundle tar file')
  parser.add_option('--tar_dir', action='store', dest='tar_dir',
                    help='destination directory for factory bundle tar')
  parser.add_option('--board2', action='store', type='string', dest='board2',
                    help='optional second target board')
  parser.add_option('--release2', action='store', dest='release2',
                    help='optional second release image for factory bundle')
  parser.add_option('--recovery2', action='store', dest='recovery2',
                    help='optional second recovery image for factory bundle')
  parser.add_option('--log_level', action='store', dest='loglevel',
                    help='console logging level: DEBUG, INFO, WARNING, ERROR')
  parser.add_option('--no_upload', action='store_false', dest='do_upload',
                    default=True,
                    help='disables upload to Google Storage for Developers')
  parser.add_option('--full_ssd', action='store_true', dest='full_ssd',
                    default=False,
                    help='makes full release image with stateful partition')
  parser.add_option('--chromeos_root', action='store', dest='chromeos_root',
                    help='root directory of ChromeOS source tree checkout')
  return parser


def HandleParseOptions():
  """Configures and retrieves options from option parser.

  Returns:
    an object, the options given to the script
    the OptionParser used to parse input options
  """
  parser = CreateParser()
  (options, args) = parser.parse_args()
  log_level = dict(DEBUG=logging.DEBUG,
                   INFO=logging.INFO,
                   WARNING=logging.WARNING,
                   ERROR=logging.ERROR)
  if options.loglevel:
    if options.loglevel not in log_level:
      raise BundlingError('Invalid logging level, please see --help and use '
                          'all caps')
    else:
      options.loglevel = log_level[options.loglevel]
  return (options, parser)


def main():
  """Main method to initiate fetching and processing of bundle components.

  Raises:
    BundlingError when image fetch or bundle processing fail.
  """
  (options, parser) = HandleParseOptions()
  if not os.path.exists(WORKDIR):
    os.makedirs(WORKDIR)
  logging.basicConfig(level=logging.DEBUG,
                      filename=os.path.join(WORKDIR, 'cros_bundle.log'))
  console = logging.StreamHandler()
  console.setLevel(options.loglevel if options.loglevel else logging.DEBUG)
  logging.getLogger('').addHandler(console)
  CheckParseOptions(options, parser)
  # TODO(benwin) run basic sanitization checks on options
  if IsInsideChroot():
    logging.error('Please run this script outside the chroot environment.')
    exit()
  if options.clean:
    logging.info('Cleaning up and exiting.')
    if os.path.exists(WORKDIR):
      shutil.rmtree(WORKDIR)
      exit()
  image_names = RunWithNamingRetries(None, FetchImages, options)
  if not image_names:
    raise BundlingError('Failed to determine URL at which to fetch images, '
                        'please check the logged URLs attempted.')
  if not options.mount_point:
    options.mount_point = MOUNT_POINT
  tarname = MakeFactoryBundle(image_names, options)
  if options.do_upload:
    UploadToGsd(tarname)


if __name__ == "__main__":
  main()
