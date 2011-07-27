#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module contains methods interfacing with pre-existing tools."""

import cb_constants
import cb_name_lib
import cb_url_lib
import cb_util_lib
import logging
import re
import os
import shutil
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

  # Modify defaults based on parameters
  if redirect_stdout:
    stdout = subprocess.PIPE
  if redirect_stderr:
    stderr = subprocess.PIPE

  try:
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=stdout, stderr=stderr)
  except OSError as (errno, strerror):
    raise BundlingError('\n'.join(['OSError [%d] : %s' % (errno, strerror),
                                   'OSError running cmd %s' % ' '.join(cmd)]))
  (cmd_result.output, cmd_result.error) = proc.communicate()
  cmd_result.returncode = proc.returncode
  if proc.returncode:
    raise BundlingError('Nonzero return code running command %s.' %
                        ' '.join(cmd))
  return cmd_result


def IsInsideChroot():
  """Returns True if we are inside chroot.

  Method borrowed from <chromeos_root>/chromite/lib/cros_build_lib.py

  Returns:
    a boolean, True if we are inside chroot.
  """
  return os.path.exists('/etc/debian_chroot')


def CheckEnvironment(image_name, firmware_dest, mount_point):
  """Checks requirements for the script to run successfully.

  In particular:
  - script is run from <ChromeOS_root>/src/scripts
  - uudecode utility is available
  - given SSD image name follows naming convention and is an existing file
  - given firmware destination is an existing directory with write access
  - mounting point is available for mounting

  Args:
    image_name: absolute file path to SSD release image binary
    firmware_dest: absolute path to directory firmware should go
    mount_point: dir to mount SSD image, defaults to cb_constants._MOUNT_POINT
  Returns:
     a boolean, True when the conditions checked are all satisfied
  """
  # TODO(benwin) refactor so this check comes at the beginning of the script
  res = True
  if not re.search('/src/scripts$', os.getcwd()):
    logging.error('\nPlease run this script from the src/scripts directory.\n')
    res = False
  cmd_result = RunCommand(['which', 'uudecode'],
                                         redirect_stdout=True)
  output_string = cmd_result.output
  if not output_string:
    logging.error('\nMissing uudecode. Please run sudo apt-get install '
                  'sharutils\n')
    res = False
  if (not os.path.isfile(image_name) or
      not re.search('.*ssd.*[.]bin$', image_name)) :
    logging.error('\nBad SSD image name given : %s\n', image_name)
    res = False
  if not os.path.isdir(firmware_dest):
    logging.error('\nFirmware destination directory %s does not exist!\n',
                  firmware_dest)
    res = False
  if not os.access(firmware_dest, os.W_OK):
    logging.error('\nFirmware destination directory %s not writable.\n',
                  firmware_dest)
    res = False
  if mount_point:
    if os.path.isdir(mount_point) and os.listdir(mount_point):
      logging.error('\nMount point %s is not emtpy!\n', mount_point)
      res = False
  else:
    logging.error('\nNo mount point specified!\n')
    res = False
  return res


def UploadToGsd(filename):
  """Uploads a file or directory to Google Storage for Developers

  Assuming proper keys for gsutil are set up for current user.

  Args:
    filename: absolute path name of file or directory to upload
  Raises:
    BundlingError when file specified by filename does not exist
  """
  if not (filename and os.path.exists(filename)):
    raise BundlingError('File %s does not exist.' % filename)
  RunCommand(['gsutil', 'cp', filename, cb_constants.GSD_BUCKET])


def ListFirmware(image_name, cros_fw):
  """Get list of strings representing contents of firmware.

  Only handles Alex firmware at present.

  Args:
    image_name: absolute file path to SSD release image binary
    cros_fw: absolute path of firmware extraction script
  Returns:
    a tuple of strings (ec_name, bios_name)
  Raises:
    BundlingError when necessary files missing.
  """
  if not os.path.exists(cros_fw):
    raise BundlingError('Necessary file chromeos-firmwareupdate missing '
                        'from %s.' % image_name)
  cmd_result = RunCommand([cros_fw, '-V'], redirect_stdout=True)
  output_string = cmd_result.output
  if not output_string:
    raise BundlingError('Failed to get output from script %s.' % cros_fw)
  lines = output_string.split('\n')
  searches = [re.search('[.]/(.*)', line) for line in lines]
  firmfiles = [match.group(1) for match in searches if match]
  if cb_constants.EC_NAME not in firmfiles:
    raise BundlingError('Necessary file ec.bin missing from %s.' % cros_fw)
  # TODO(benwin) add additional branching for h2c binary
  if cb_constants.BIOS_NAME not in firmfiles:
    raise BundlingError('Necessary file bios.bin missing from %s.' % cros_fw)
  ec_name = cb_constants.EC_NAME
  ec_pat = re.compile('EC image:.*(Alex.*)')
  ec_searches = [ec_pat.search(line) for line in lines]
  ec_matches = [match.group(1) for match in ec_searches if match]
  if len(ec_matches):
    ec_name = ec_matches[0]
  else:
    logging.warning('Proper renaming of ec.bin firmware failed.')
  bios_name = cb_constants.BIOS_NAME
  bios_pat = re.compile('BIOS image:.*(Alex.*)')
  bios_searches = [bios_pat.search(line) for line in lines]
  bios_matches = [match.group(1) for match in bios_searches if match]
  if len(bios_matches):
    bios_name = bios_matches[0]
  else:
    logging.warning('Proper renaming of bios.bin firmware failed.')
  return (ec_name, bios_name)


def ExtractFiles(cros_fw):
  """Extract necessary firmware files from an SSD image.

  Args:
    cros_fw: absolute path of firmware extraction script
  Returns:
    a string, directory of extracted files, None on failure
  """
  if not os.path.exists(cros_fw):
    logging.error('Necessary firmware extraction script %s missing.', cros_fw)
    return None
  cmd_result = RunCommand([cros_fw, '--sb_extract'], redirect_stdout=True)
  output_string = cmd_result.output
  firmdir = ''
  dirsearch = re.search('/tmp/tmp[.].*', output_string)
  if dirsearch:
    firmdir = dirsearch.group()
  if (not firmdir) or (not os.path.exists(firmdir)):
    logging.warning('Failed to extract necessary firmware directory.')
    return None
  return firmdir


def ExtractFirmware(image_name, firmware_dest, mount_point):
  """Extract firmware from an SSD image to help prepare a factory bundle.

  Requires current directory to be <ChromeOS_root>/src/scripts.
  Requires sudoer password entry to mount SSD image.
  Requires use of uudecode utility available in package sharutils.
  Requires mount_point is free to mount SSD image.
  Requires firmware destination directory exists and is writable.

  Args:
    image_name: absolute file path to SSD release image binary
    firmware_dest: absolute path to directory firmware should go
    mount_point: dir  to mount SSD image, defaults to cb_constants._MOUNT_POINT
  Returns:
    a boolean, True when the firmware has been successfully extracted
  Raises:
    BundlingError when necessary tools are missing or SSD mounting fails.
  """
  if not CheckEnvironment(image_name, firmware_dest, mount_point):
    raise BundlingError('Environment check failed, please fix conditions '
                        'listed above.')
  image = image_name.split(os.sep)[-1]
  try:
    # mount SSD image at mount_point
    logging.info('Mounting SSD image.')
    RunCommand(['./mount_gpt_image.sh', '--read_only', '--safe',
                '--from=' + cb_constants.TMPDIR, '--image=' + image,
                '--rootfs_mountpt=' + mount_point])
    if not os.path.exists(mount_point) or not os.listdir(mount_point):
      raise BundlingError('Failed to mount SSD image at mount point %s' %
                          mount_point)
    cros_fw = os.path.join(mount_point, 'usr', 'sbin',
                           'chromeos-firmwareupdate')
    (ec_name, bios_name) = ListFirmware(image_name, cros_fw)
    firmdir = ExtractFiles(cros_fw)
    if not firmdir:
      raise BundlingError('Failed to extract firmware files.')
    shutil.copy(os.path.join(firmdir, cb_constants.EC_NAME),
                os.path.join(firmware_dest, ec_name))
    shutil.copy(os.path.join(firmdir, cb_constants.BIOS_NAME),
                os.path.join(firmware_dest, bios_name))
    shutil.copy(cros_fw, firmware_dest)
  finally:
    RunCommand(['./mount_gpt_image.sh', '--unmount'])
  filename = os.path.join(cb_constants.TMPDIR, image_name)
  md5filename = filename + '.md5'
  if not cb_util_lib.CheckMd5(filename, md5filename):
    logging.error('SSD image MD5 checksum did not match, image was corrupted!')
    return False
  return True


def ConvertRecoveryToSsd(image_name, board, recovery, force):
  """Converts a recovery image into an SSD image.

  Args:
    image_name: absolute path name of recovery image to convert
    board: board name of recovery image to convert
    recovery: recovery image version/channel/signing_key
    force: a boolean, True when any existing bundle files can be deleted
  Returns:
    a string, the absolute path name of the extracted SSD image
  Throws:
    BundlingError when resources not found or conversion fails.
  """
  # TODO(benwin) refactor to modularize
  # fetch convert_recovery_to_full_ssd.sh
  if os.path.exists(cb_constants.GITDIR):
    if force:
      shutil.rmtree(cb_constants.GITDIR)
      os.mkdir(cb_constants.GITDIR)
    else:
      raise BundlingError('Directory to git clone exists, use -f to overwrite')
  RunCommand(['git', 'clone', cb_constants.GITURL, cb_constants.GITDIR])
  # fetch zip containing chromiumos_base_image
  try:
    index_page, rec_pat = cb_name_lib.GetRecoveryName(board, recovery)
    rec_url = cb_url_lib.DetermineUrl(index_page, rec_pat)
  except cb_url_lib.NameResolutionError:
    index_page, rec_pat = cb_name_lib.GetRecoveryName(board,
                                          recovery,
                                          alt_naming=True)
    rec_url = cb_url_lib.DetermineUrl(index_page, rec_pat)
  if not rec_url:
    raise BundlingError('Could not find match for pattern %s at %s.' %
                        (rec_pat, rec_url))
  rec_no = recovery.split('/')[0]
  zip_pat = '-'.join(['ChromeOS', rec_no, '.*', board + '.zip'])
  zip_url = cb_url_lib.DetermineUrl(index_page, zip_pat)
  if not cb_url_lib.Download(zip_url):
    raise BundlingError('Failed to download %s.' % zip_url)
  zip_name = os.path.join(cb_constants.TMPDIR, os.path.basename(zip_url))
  ssd_name = image_name.replace('recovery', 'ssd')
  if os.path.exists(ssd_name):
    if not force:
      raise BundlingError('File named %s already exists, use -f to overwrite' %
                          ssd_name)
  # put cgpt in the path
  au_gen_url = os.path.join(index_page, cb_constants.AU_GEN)
  if not cb_url_lib.Download(au_gen_url):
    raise BundlingError('Necessary resource %s could not be fetched.' %
                        au_gen_url)
  au_gen_name = os.path.join(cb_constants.TMPDIR, cb_constants.AU_GEN)
  cgpt_name = os.path.join(cb_constants.TMPDIR, 'cgpt')
  if not cb_util_lib.ZipExtract(au_gen_name, 'cgpt', path=cb_constants.TMPDIR):
    raise BundlingError('Could not extract necesary resource %s from %s.' %
                        (cgpt_name, au_gen_name))
  cgpt_dest = os.path.join(cb_constants.SUDO_DIR, 'cgpt')
  if os.path.exists(cgpt_dest):
    if force:
      RunCommand(['sudo', 'cp', cgpt_name, cgpt_dest])
    else:
      raise BundlingError('Necessary utility cgpt already exists at %s, use '
                          '-f to overwrite with newest version.' %
                          cgpt_dest)
  else:
    RunCommand(['sudo', 'cp', cgpt_name, cgpt_dest])
  # execute script
  script_name = os.path.join(cb_constants.GITDIR,
                             'scripts',
                             'image_signing',
                             'convert_recovery_to_full_ssd.sh')
  RunCommand([script_name, image_name, zip_name, ssd_name])
  # TODO(benwin) consider cleaning up resources based on command line flag
  return ssd_name
