#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module contains common constants for factory bundle process."""

import logging
import os


# Keep constants in ascending alphabetical order
AU_GEN = 'au-generator.zip'
BIOS_NAME = 'bios.bin'
EC_NAME = 'ec.bin'
EC2_NAME = 'Alex_EC_VFA616M.bin'
GITURL = 'http://git.chromium.org/chromiumos/platform/vboot_reference.git'
# TODO(benwin) update to production value once it is determined
GSD_BUCKET = 'gs://chromeos-download-test'
IMAGE_GSD_BUCKET = 'gs://chromeos-releases'
IMAGE_GSD_PREFIX = 'https://sandbox.google.com/storage/chromeos-releases'
IMAGE_SERVER_PREFIX = 'http://chromeos-images/chromeos-official'
MOUNT_POINT = '/tmp/m'
SUDO_DIR = '/usr/local/sbin'
WORKDIR = '/usr/local/google/cros_bundle/tmp'
# GITDIR should be defined after WORKDIR
GITDIR = os.path.join(WORKDIR, 'vboot_reference')


class BundlingError(Exception):
  """Common exception for bundling process errors."""
  def __init__(self, reason):
    Exception.__init__(self, reason)
    logging.error('Script exiting due to:\n' + reason + '\n')
