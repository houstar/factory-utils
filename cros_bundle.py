#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This script repackages ChromeOS images into a factory bundle.

This script runs outside the chroot environment in the
<chromeos_root>/src/scripts directory.
Assuming sufficient disk space in /usr partition, at least 20 GB free.
Names bundle factory_bundle_yyyy_mm_dd.tar.bz2
Two bundles in one day can cause naming conflicts, deleting all stored files
  with option --clean is recommended between uses on a single day.

Usage: to download and repackage factory bundle files, convert recovery to ssd
       cd /home/$USER/chromiumos/src/scripts
       python ../platform/factory-utils/cros_bundle.py
       --board x86-alex --recovery 0.12.433.269/stable/mp
       --factory 0.12.433.269/stable

       -OR-

       to download and repackage factory bundle files with multiple images,
         converting recovery to ssd for both images
       cd /home/$USER/chromiumos/src/scripts
       python ../platform/factory-utils/cros_bundle.py
       --board x86-alex --recovery 0.12.433.269/stable/mp
       --board2 x86-alex-nogobi --recovery2 0.12.433.269/stable/mp
       --factory 0.12.433.269/stable

       -OR-

       to clean all files in temporary directory
       python cros_bundle.py --clean

       -OR-

       to see this message
       python cros_bundle.py --help
"""

import cb_command_lib
import cb_constants
import cb_url_lib
import cros_bundle_lib
import logging
import os
import shutil

from cb_constants import BundlingError
from optparse import OptionParser


def HandleParseOptions():
  """Configures and retrieves options from option parser.

  Returns:
    an object, the options given to the script
    the OptionParser used to parse input options
  """
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
                    help='absolute path to directory for factory bundle files')
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
  if not os.path.exists(cb_constants.TMPDIR):
    os.makedirs(cb_constants.TMPDIR)
  logging.basicConfig(level=logging.DEBUG,
                      filename=os.path.join(cb_constants.TMPDIR,
                                            'cros_bundle.log'))
  console = logging.StreamHandler()
  console.setLevel(options.loglevel if options.loglevel else logging.DEBUG)
  logging.getLogger('').addHandler(console)
  cros_bundle_lib.CheckParseOptions(options, parser)
  # TODO(benwin) run basic sanitization checks on options
  if cb_command_lib.IsInsideChroot():
    logging.error('Please run this script outside the chroot environment.')
    exit()
  if options.clean:
    logging.info('Cleaning up and exiting.')
    if os.path.exists(cb_constants.TMPDIR):
      shutil.rmtree(cb_constants.TMPDIR)
      exit()
  try:
    # try default naming scheme
    image_names = cros_bundle_lib.FetchImages(options)
  except cb_url_lib.NameResolutionError:
    logging.info('Trying alternative naming scheme')
    image_names = cros_bundle_lib.FetchImages(options, alt_naming=True)
  if not options.mount_point:
    options.mount_point = cb_constants.MOUNT_POINT
  tarname = cros_bundle_lib.MakeFactoryBundle(image_names, options)
  if options.do_upload:
    cb_command_lib.UploadToGsd(tarname)


if __name__ == "__main__":
  main()
