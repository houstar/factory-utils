#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module contains common constants for factory bundle process."""

import logging
import os

WORKDIR = '/usr/local/google/cros_bundle/tmp'
PREFIX = 'http://chromeos-images/chromeos-official'
EC_NAME = 'ec.bin'
EC2_NAME = 'Alex_EC_VFA616M.bin'
BIOS_NAME = 'bios.bin'
MOUNT_POINT = '/tmp/m'
GITURL = 'http://git.chromium.org/chromiumos/platform/vboot_reference.git'
GITDIR = os.path.join(WORKDIR, 'vboot_reference')
# TODO(benwin) update to production value once it is determined
GSD_BUCKET = 'gs://chromeos-download-test'
AU_GEN = 'au-generator.zip'
SUDO_DIR = '/usr/local/sbin'


class BundlingError(Exception):
  """Common exception for bundling process errors."""
  def __init__(self, reason):
    Exception.__init__(self, reason)
    logging.error('Script exiting due to:\n' + reason + '\n')
