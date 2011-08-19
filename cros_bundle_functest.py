#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functional testing for the cros_bundle main script module."""

import logging
import os
import unittest

from cb_command_lib import RunCommand


def _MapOptions(options):
  """Map option-value pairs to command-line format.

  Args:
    options: a dict whose keys are options and values are matching values
  Returns:
    a list, extending by [--option, value] for each input pair
  """
  option_list = []
  for key in options:
    option_list.append('--' + key)
    option_list.append(options[key])
  return option_list


class TestCrosBundle(unittest.TestCase):
  """Testing for main cros_bundle script."""

  def tearDown(self):
    logging.info('\nAssuming ChromeOS Root is /home/$USER/chromiumos\n')
    cwd = '/home/' + os.environ['USER'] + '/chromiumos/src/scripts'
    cmd = ['python', '../platform/factory-utils/cros_bundle.py']
    cmd.extend(['--clean'])
    logging.debug('Running command: ' + ' '.join(cmd) + ' in ' + cwd)
    RunCommand(cmd, cwd=cwd)

  def testFSIBundleCreation(self):
    """Functional test of the generation of an FSI factory bundle.

    In particular we implement the sample usage command for two input images
    with recovery to ssd conversion required for each.
    """
    logging.info('\nAssuming ChromeOS Root is /home/$USER/chromiumos\n')
    cwd = '/home/' + os.environ['USER'] + '/chromiumos/src/scripts'
    options = {'board':'x86-alex',
               'recovery':'0.15.916.0/dev/mp',
               'board2':'x86-alex-he',
               'recovery2':'0.15.916.0/dev/mp',
               'factory':'0.15.916.0/dev',
               }
    cmd = ['python', '../platform/factory-utils/cros_bundle.py']
    cmd.extend(_MapOptions(options))
    cmd.extend(['--fsi', '-f', '--no_upload'])
    logging.debug('Running command: ' + ' '.join(cmd) + ' in ' + cwd)
    cmd_res = RunCommand(cmd, cwd=cwd)
    self.assertEqual(cmd_res.returncode, 0)

#  Non-fsi test disabled due to lack of image with published install shim
#
#  def testFactoryBundleCreation(self):
#    """Functional test of the generation of a factory bundle.
#
#    In particular we implement the sample usage command for one input image
#    with recovery to ssd conversion required and install shim needed.
#    """
#    logging.info('\nAssuming ChromeOS Root is /home/$USER/chromiumos\n')
#    cwd = '/home/' + os.environ['USER'] + '/chromiumos/src/scripts'
#    options = {'board':'x86-alex',
#               'recovery':'0.13.587.116/beta/mp',
#               'factory':'0.13.587.116/beta',
#               'shim':'0.13.587.116/dev/mp',
#               }
#    cmd = ['python', '../platform/factory-utils/cros_bundle.py']
#    cmd.extend(_MapOptions(options))
#    cmd.extend(['-f', '--no_upload'])
#    logging.debug('Running command: ' + ' '.join(cmd) + ' in ' + cwd)
#    cmd_res = RunCommand(cmd, cwd=cwd)
#    self.assertEqual(cmd_res.returncode, 0)


if __name__ == "__main__":
  logging.basicConfig(level=logging.DEBUG)
  unittest.main()
