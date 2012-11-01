#!/usr/bin/python
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This script runs inside chroot environment. It places new factory tests in the
appropriate directories of the given factory image. All paths should be
specified relative to the chroot environment.

E.g.: private_factory_suite --image=bin --tests=dir --test_list=list
"""

import distutils.dir_util
import distutils.file_util
import optparse
import os
import subprocess
import sys


# Paths to factory directories on host
_PLATFORMS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
_MOUNT_SCRIPT_REL_PATH = 'factory/bin/mount_partition'
_MOUNT_PARTITION_SCRIPT = os.path.join(_PLATFORMS_DIR, _MOUNT_SCRIPT_REL_PATH)

# Constants consumed by mount_partition
_MOUNT_POINT = '/media'
_MOUNT_PARTITION_INDEX = '1'
_MOUNT_RW = '-rw'

# Paths to test directories on image, relative to _MOUNT_POINT
_IMAGE_TEST_DIR = 'dev_image/autotest/client/site_tests/'
_IMAGE_TEST_LIST = 'dev_image/factory/custom/test_list'

def ModFactoryImage(factory_bin, test_src, test_list_src):
  """Adds new tests and a test_list to the given factory image.

  Args:
    factory_bin: path to factory image file.
    test_src: path to directory containing tests.
    test_list_src: path to test list.

  Raises:
    CalledProcessError: if a script or command returns non-zero.
    DistutilsFileError: on file copy failure.
  """
  subprocess.check_call([_MOUNT_PARTITION_SCRIPT,
                         _MOUNT_RW, factory_bin,
                         _MOUNT_PARTITION_INDEX, _MOUNT_POINT])
  try:
    test_sink = os.path.join(_MOUNT_POINT, _IMAGE_TEST_DIR)
    test_list_sink = os.path.join(_MOUNT_POINT,_IMAGE_TEST_LIST)
    distutils.dir_util.copy_tree(test_src, test_sink)
    distutils.file_util.copy_file(test_list_src, test_list_sink)
  finally:
    subprocess.check_call(['umount', _MOUNT_POINT])


def ParseOptions():
  """Parses given options.

  Raises:
    OptionError: if mandatory input parameters are not supplied
  """
  parser = optparse.OptionParser()
  parser.add_option(
      '--image',
      dest = "image",
      default = None,
      help = 'path to chromiumos_factory_image.bin.'
  )
  parser.add_option(
      '--tests',
      dest = "tests",
      default = None,
      help = 'path to directory containing all tests.'
  )
  parser.add_option(
      '--test_list',
      dest = "test_list",
      default = None,
      help = 'test list containing tests.'
  )
  options = parser.parse_args()[0]
  if not options.image:
    parser.error('supply bin location with --image=')

  if not options.tests:
    parser.error('supply test directory location with --tests=')

  if not options.test_list:
    parser.error('supply test_list location with --test_list=')
  return options


def main():
  options = ParseOptions()
  ModFactoryImage(options.image,
                  options.tests,
                  options.test_list)


if __name__ == '__main__':
  main()