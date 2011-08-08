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

  def testBundleCreation(self):
    """Functional test of the generation of a factory bundle.

    In particular we implement the sample usage command for two input images
    with recovery to ssd conversion required for each.
    """
    logging.info('\nAssuming ChromeOS Root is /home/$USER/chromiumos\n')
    cwd = '/home/' + os.environ['USER'] + '/chromiumos/src/scripts'
    options = {'board':'x86-alex',
               'recovery':'0.12.433.269/stable/mp',
               'board2':'x86-alex-nogobi',
               'recovery2':'0.12.433.269/stable/mp',
               'factory':'0.12.433.269/stable',
               }
    cmd = ['python', '../platform/factory-utils/cros_bundle.py']
    cmd.extend(_MapOptions(options))
    cmd.extend(['-f', '--no_upload'])
    logging.debug('Running command: ' + ' '.join(cmd) + ' in ' + cwd)
    cmd_res = RunCommand(cmd, cwd=cwd)
    self.assertEqual(cmd_res.returncode, 0)


if __name__ == "__main__":
  logging.basicConfig(level=logging.DEBUG)
  unittest.main()
