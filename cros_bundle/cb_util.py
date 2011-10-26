#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module contains methods interfacing with pre-existing tools."""

import logging
import subprocess

from cb_constants import BundlingError


class CommandResult(object):
  """An object to store various attributes of a child process.

  Borrowed from <chromeos_root>/chromite/lib/cros_build_lib.py
  """
  def __init__(self):
    self.cmd = None
    self.error = None
    self.output = None
    self.returncode = None


def RunCommand(cmd, redirect_stdout=False, redirect_stderr=False, cwd=None):
  """Runs a command using subprocess module Popen.

  Blocks until command returns.
  Modeled on RunCommand from <chromeos_root>/chromite/lib/cros_build_lib.py

  Args:
    cmd: a list of arguments to Popen
    redirect_stdout: a boolean, True when subprocess output should be returned
    redirect_stderr: a boolean, True when subprocess errors should be returned
    cwd: working directory in which to run command
  Returns:
    a CommandResult object.
  Raises:
    BundlingError when running command fails.
  """
  # Set default
  stdout = None
  stderr = None
  cmd_result = CommandResult()
  cmd_result.cmd = cmd

  # Modify defaults based on parameters
  if redirect_stdout:
    stdout = subprocess.PIPE
  if redirect_stderr:
    stderr = subprocess.PIPE

  # log command run
  logging.info('Running command: ' + ' '.join(cmd))

  try:
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=stdout, stderr=stderr)
  except OSError as (errno, strerror):
    raise BundlingError('\n'.join(['OSError [%d] : %s' % (errno, strerror),
                                   'OSError running cmd %s' % ' '.join(cmd)]))
  (cmd_result.output, cmd_result.error) = proc.communicate()
  cmd_result.returncode = proc.returncode
  return cmd_result
