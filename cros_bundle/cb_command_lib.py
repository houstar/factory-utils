#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module contains methods interfacing with pre-existing tools."""

import cb_constants
import logging
import re
import os
import shutil

from cb_archive_hashing_lib import CheckMd5, ZipExtract
from cb_name_lib import ResolveRecoveryUrl, RunWithNamingRetries
from cb_url_lib import DetermineUrl, Download
from cb_util import RunCommand

USER = os.environ['USER']
HOME_DIR = '/home/%s/trunk/src' % USER
IMG_SIGN_DIR = HOME_DIR + '/platform/vboot_reference/scripts/image_signing'
CHROOT_ROOT = '/home/%s/chromiumos/chroot' % USER
CHROOT_REL_DIR = 'tmp/bundle_tmp'

# Mapping of firmware internal name to regular expression patterns.
FIRMWARE_MAP = {
    'x86-alex': {
        'ec': {'name': cb_constants.EC_NAME['x86-alex'],
               'pattern': 'EC image:.*(Alex.*)'},
        'ec2': {'name': cb_constants.EC2_NAME['x86-alex'],
                'pattern': 'Extra file:.*(Alex.*)'},
        'bios': {'name': cb_constants.BIOS_NAME['x86-alex'],
                 'pattern': 'BIOS image:.*(Alex.*)'}
        },
    'stumpy': {
        'bios': {'name': cb_constants.BIOS_NAME['stumpy'],
                 'pattern': 'BIOS image:.*(Stumpy.*)'}
        },
    }


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
    image_name: a string, absolute file path to SSD release image binary.
    firmware_dest: a string, absolute path to directory firmware should go.
    mount_point: a string, directory to mount SSD image. Defaults to
                 cb_constants._MOUNT_POINT
  Returns:
    a boolean, True when the conditions checked are all satisfied.
  """
  # TODO(benwin) refactor so this check comes at the beginning of cros_bundle.py
  res = True
  if not re.search('/src/scripts$', os.getcwd()):
    logging.error('\nPlease run this script from the src/scripts directory.\n')
    res = False
  cmd_result = RunCommand(['which', 'uudecode'], redirect_stdout=True)
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
    raise cb_constants.BundlingError('File %s does not exist.' % filename)
  RunCommand(['gsutil', 'cp', filename, cb_constants.GSD_BUCKET])


def _ExtractFirmwareFilename(fw_type, board, fw_content):
  """Parses chromeos-firmwareupdate output for proper firmware file name.

  Background:
   - factory ssd image comes with a binary executable 'chromeos-firmwareupdate'
   - we use this executable to extract EC firmware for Alex (i.e. 'ec.bin')
   - for Alex factory bundle, use an alternative name for this EC firmware

  Sample output of chromeos-firmwareupdate command (truncated):
    EC image:     4d02c93315c880efdfc50ef12b281c9e \
    */build/x86-alex_he/tmp/portage/chromeos-base/<SNIP>/Alex_EC_XHA002M.bin
    <--snip-->
    Package Content:
    4d02c93315c880efdfc50ef12b281c9e *./ec.bin

  In this example, we want to rename 'ec.bin' as 'Alex_EC_XHA002M.bin' in the
  output bundle (both lines contain the same hash value).

  Args:
    fw_type: a string, type of firmware. Valid values are keys in FIRMWARE_MAP.
    board: a string, target board.
    fw_content: a list of strings, output of 'chromeos-firmwareupdate -V'.

  Returns:
    rename: a string, desired firmware filename. Or None if no match found.
  """
  rename = FIRMWARE_MAP[board][fw_type]['name']
  fw_pat = re.compile(FIRMWARE_MAP[board][fw_type]['pattern'])
  fw_searches = [fw_pat.search(line) for line in fw_content]
  fw_matches = [match.group(1) for match in fw_searches if match]
  if fw_matches:
    #TODO(tgao): ask factory team if this should be an error condition
    if len(fw_matches) > 1:
      logging.warning('Multiple matches of firmware names: fw_type = %r, '
                      'board = %r', fw_type, board)
    if rename != fw_matches[0]:
      return fw_matches[0]

  #TODO(tgao): ask factory team if this should be an error condition
  logging.warning('Proper renaming of firmware %s failed.', rename)
  return rename


def ListFirmware(image_name, cros_fw, board):
  """Gets list of strings representing contents of firmware.

  As of 11/2011, only handles Alex and Stumpy firmwares.

  Args:
    image_name: a string, absolute file path to SSD release image binary.
    cros_fw: a string, absolute path of firmware extraction script.
    board: a string, target board.

  Returns:
    a dict, {fw_type: fw_name}.

  Raises:
    BundlingError when necessary files missing.
  """
  if not os.path.exists(cros_fw):
    err = 'File chromeos-firmwareupdate missing from %s.' % image_name
    raise cb_constants.BundlingError(err)

  cmd_result = RunCommand([cros_fw, '-V'], redirect_stdout=True)
  output = cmd_result.output
  if not output:
    err = 'Failed to get output from script %s.' % cros_fw
    raise cb_constants.BundlingError(err)

  logging.debug('ListFirmware(): chromeos-firmwareupdate output = %s', output)
  fw_content = output.split('\n')
  pat = re.compile('[.]/(.*)')
  # Look for mandatory firmware files in chromeos-firmwareupdate output.
  # For example, if fw_content = """
  # Package Content:
  #   57350ea0958cb39a715ddd4ccf2f0e92 *./bios.bin"""
  # searches = [None, None, <sre.SRE_Match object at 0x...>, ]
  # fw_files = ['bios.bin']
  searches = [pat.search(line) for line in fw_content]
  fw_files = [match.group(1) for match in searches if match]
  for f in [FIRMWARE_MAP[board][k]['name'] for k in FIRMWARE_MAP[board].keys()]:
    if f not in fw_files:
      raise cb_constants.BundlingError('Necessary file %s missing from %s.' %
                                       (f, cros_fw))

  fw_names = dict()
  for fw_type in FIRMWARE_MAP[board].keys():
    fw_names[fw_type] = _ExtractFirmwareFilename(fw_type, board, fw_content)
  return fw_names


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
  # TODO(benwin) can this regex be future-proofed?
  dirsearch = re.search('/tmp/tmp[.].*', output_string)
  if dirsearch:
    firmdir = dirsearch.group()
    if firmdir and os.path.exists(firmdir):
      return firmdir
  logging.warning('Failed to extract necessary firmware directory.')
  return None


def ExtractFirmware(image_name, firmware_dest, mount_point, board):
  """Extract firmware from an SSD image to help prepare a factory bundle.

  See docstring of CheckEnvironment() for environmental prerequisites.

  Args:
    image_name: a string, absolute file path to SSD release image binary.
    firmware_dest: a string, absolute path to directory firmware should go.
    mount_point: a string, directory to mount SSD image.
    board: a string, target board.
  Raises:
    BundlingError when necessary tools are missing or SSD mounting fails.
  """
  if not CheckEnvironment(image_name, firmware_dest, mount_point):
    raise cb_constants.BundlingError(
        'Environment check failed, please fix conditions listed above.')

  image = os.path.basename(image_name)
  try:
    logging.info('Mounting SSD image.')
    cmd_result = RunCommand([
        './mount_gpt_image.sh', '--read_only', '--safe',
        '='.join(['--from', cb_constants.WORKDIR]),
        '='.join(['--image', image]),
        '='.join(['--rootfs_mountpt', mount_point])
       ])
    if not os.path.exists(mount_point) or not os.listdir(mount_point):
      err = ('Failed to mount SSD image at %s: cmd_result = %r' %
             (mount_point, cmd_result))
      raise cb_constants.BundlingError(err)

    cros_fw = os.path.join(mount_point, 'usr', 'sbin',
                           'chromeos-firmwareupdate')
    fw_name = ListFirmware(image_name, cros_fw, board)
    firmdir = ExtractFiles(cros_fw)
    if not firmdir:
      raise cb_constants.BundlingError('Failed to extract firmware files.')

    for k, v in FIRMWARE_MAP[board].iteritems():
      src_path = os.path.join(firmdir, v['name'])
      if not os.path.exists(src_path):
        logging.debug('shutil: skip non-existing file %s', src_path)
        continue
      dst_path = os.path.join(firmware_dest, fw_name[k])
      shutil.copy(src_path, dst_path)

    # Per yongjaek in 11/2011, also copy chromeos-firmwareupdate shellball
    shutil.copy(cros_fw, firmware_dest)
  finally:
    RunCommand(['./mount_gpt_image.sh', '--unmount'])

  filename = os.path.join(cb_constants.WORKDIR, image_name)
  md5filename = filename + '.md5'
  if not CheckMd5(filename, md5filename):
    raise cb_constants.BundlingError(
        'SSD image MD5 check failed, image was corrupted!')


def HandleGitExists(force):
  """Detect if git directory already exists and handle overwrite confirmation.

  Args:
    force: a boolean, True when all existing bundle files can be deleted
  Raises:
    BundlingError when git directory exists and user does not confirm overwrite
  """
  if os.path.exists(cb_constants.GITDIR):
    if force:
      shutil.rmtree(cb_constants.GITDIR)
      os.mkdir(cb_constants.GITDIR)
    else:
      msg = ('Old recovery conversion script git repo exists, please '
             'confirm overwrite')
      if AskUserConfirmation(msg):
        shutil.rmtree(cb_constants.GITDIR)
        os.mkdir(cb_constants.GITDIR)
      else:
        raise cb_constants.BundlingError(
            'Vboot git repo exists, use -f to update')
  else:
    os.mkdir(cb_constants.GITDIR)


def HandleSsdExists(ssd_name, force):
  """Detect if ssd image already exists and handle overwrite confirmation.

  Args:
    ssd_name: absolute path name of ssd image to check for
    force: a boolean, True when all existing bundle files can be deleted
  Raises:
    BundlingError when ssd image exists and user does not confirm overwrite
  """
  if os.path.exists(ssd_name):
    if not force:
      msg = 'SSD file %s already exists, please confirm overwrite' % ssd_name
      if not AskUserConfirmation(msg):
        raise cb_constants.BundlingError(
            'File %s already exists, use -f to overwrite' % ssd_name)


def MoveCgpt(cgpt_file, dest_file):
  """Concentrate logic to move cgpt and assign permissions.

  Args:
    cgpt_file: absolute path to cgpt file
    dest_file: absolute pathname of file destination
  """
  RunCommand(['sudo', 'cp', cgpt_file, dest_file])
  RunCommand(['sudo', 'chmod', '760', dest_file])


def InstallCgpt(index_page, force):
  """Install necessary cgpt utility on the sudo path.

  Args:
    index_page: html page to download au-generator containing correct cgpt
    force: a boolean, True when all existing bundle files can be deleted
  Raises:
    BundlingError when resource fetch and extract fails or overwrite is denied
  """
  au_gen_url = os.path.join(index_page, cb_constants.AU_GEN)
  if not Download(au_gen_url):
    raise cb_constants.BundlingError(
        'Necessary resource %s could not be fetched.' % au_gen_url)
  au_gen_name = os.path.join(cb_constants.WORKDIR, cb_constants.AU_GEN)
  cgpt_name = os.path.join(cb_constants.WORKDIR, 'cgpt')
  if not ZipExtract(au_gen_name, 'cgpt', path=cb_constants.WORKDIR):
    raise cb_constants.BundlingError(
        'Could not extract necesary resource %s from %s.' %
        (cgpt_name, au_gen_name))
  cgpt_dest = os.path.join(cb_constants.SUDO_DIR, 'cgpt')
  if os.path.exists(cgpt_dest):
    if force:
      MoveCgpt(cgpt_name, cgpt_dest)
    else:
      msg = 'cgpt exists at %s, please confirm update' % cgpt_dest
      if AskUserConfirmation(msg):
        MoveCgpt(cgpt_name, cgpt_dest)
      else:
        raise cb_constants.BundlingError(
            'Necessary utility cgpt already exists at %s, use -f to overwrite '
            'with newest version.' % cgpt_dest)
  else:
    MoveCgpt(cgpt_name, cgpt_dest)


def ConvertRecoveryToSsd(image_name, options):
  """Converts a recovery image into an SSD image.

  Default ssd option requires chroot setup and script running in src/scripts.

  Args:
    image_name: absolute path name of recovery image to convert
    options: an object containing inputs to the script
      please see cros_bundle_lib/CheckBundleInputs for possibilities
  Returns:
    a string, the absolute path name of the extracted SSD image
  """
  if options.full_ssd:
    # TODO(benwin) convert recovery image to full ssd image inside chroot
    return RecoveryToFullSsdNoChroot(image_name, options)
  return RecoveryToStandardSsd(image_name, options)


def RecoveryToFullSsdNoChroot(image_name, options):
  """Converts a recovery image into an SSD image with stateful partition.

  This method does not depend on a chroot setup.

  Args:
    image_name: absolute path name of recovery image to convert
    options: an object containing inputs to the script
      please see cros_bundle_lib/CheckBundleInputs for possibilities
  Returns:
    a string, the absolute path name of the extracted SSD image
  Raises:
    BundlingError when resources not found or conversion fails.
  """
  force = options.force
  board = options.board
  recovery = options.recovery
  ssd_name = image_name.replace('recovery', 'ssd')
  HandleSsdExists(ssd_name, force)
  # fetch convert_recovery_to_full_ssd.sh
  HandleGitExists(force)
  RunCommand(['git', 'clone', cb_constants.GITURL, cb_constants.GITDIR])
  # fetch zip containing chromiumos_base_image
  (rec_url, index_page) = RunWithNamingRetries(
      None, ResolveRecoveryUrl, board, recovery)
  if not index_page:
    raise cb_constants.BundlingError(
        'All naming schemes failed attempting to resolve recovery URL '
        'for recovery version %s' % recovery)
  if not rec_url:
    raise cb_constants.BundlingError(
        'Could not find URL match for recovery version %s on page %s' %
        (recovery, index_page))
  rec_no = recovery.split('/')[0]
  token_list = ['chromeos', rec_no, board,  '.zip']
  zip_url = DetermineUrl(index_page, token_list)
  if not zip_url:
    raise cb_constants.BundlingError(
        'Failed to determine name of zip file for token_list %s on page %s' %
        (token_list, index_page))
  if not Download(zip_url):
    raise cb_constants.BundlingError('Failed to download %s.' % zip_url)
  zip_name = os.path.join(cb_constants.WORKDIR, os.path.basename(zip_url))
  InstallCgpt(index_page, force)
  script_name = os.path.join(cb_constants.GITDIR,
                             'scripts',
                             'image_signing',
                             'convert_recovery_to_full_ssd.sh')
  RunCommand([script_name, image_name, zip_name, ssd_name])
  # TODO(benwin) consider cleaning up resources based on command line flag
  return ssd_name


def RecoveryToStandardSsd(image_name, options):
  """Converts a recovery image into an SSD image.

  Assumes a chroot setup.
  Requires sudo privileges to run cros_sdk.
  Requires the script to run in <ChromeOS_root>/src/scripts.

  Args:
    image_name: absolute path name of recovery image to convert
    options: an object containing inputs to the script
      please see cros_bundle_lib/CheckBundleInputs for possibilities
  Returns:
    a string, the absolute path name of the extracted SSD image
  Raises:
    BundlingError when resources not found or conversion fails.
  """
  force = options.force
  chromeos_root = options.chromeos_root
  if not re.search('/src/scripts$', os.getcwd()):
    raise cb_constants.BundlingError(
        'ConvertRecoveryToSsd must be run from src/scripts.')
  image_dir = os.path.dirname(image_name)
  ssd_name = image_name.replace('recovery', 'ssd')
  HandleSsdExists(ssd_name, force)
  # make copy of recovery image to consume
  if not options.chromeos_root:
    chroot_work_dir = os.path.join(CHROOT_ROOT, CHROOT_REL_DIR)
  else:
    if not (chromeos_root and os.path.isdir(chromeos_root)):
      raise cb_constants.BundlingError(
          'Provided ChromeOS source tree root %s does not exist or '
          'is not a directory' % chromeos_root)
    chroot_work_dir = os.path.join(chromeos_root, 'chroot', CHROOT_REL_DIR)
  # ensure we have a chroot to work in
  chroot_work_parent_dir = re.match('(.*/).*', chroot_work_dir).group(1)
  if not os.path.exists(chroot_work_parent_dir):
    raise cb_constants.BundlingError(
        'Chroot environment could not be inferred, failed to create link %s.' %
        chroot_work_dir)
  if not(chroot_work_dir and os.path.isdir(chroot_work_dir)):
    os.mkdir(chroot_work_dir)
  ssd_chroot_name = ssd_name.replace(image_dir, chroot_work_dir)
  shutil.copy(image_name, ssd_chroot_name)
  cmd = (['cros_sdk',
          '--',
          os.path.join(IMG_SIGN_DIR, 'convert_recovery_to_ssd.sh'),
          ssd_name.replace(image_dir,
                           ReinterpretPathForChroot(chroot_work_dir))])
  if options.force:
    cmd.insert(5, '--force')
  RunCommand(cmd)
  # move ssd out, clean up folder
  shutil.move(ssd_chroot_name, ssd_name)
  shutil.rmtree(chroot_work_dir)
  return ssd_name


def FindRepoDir(path=None):
  """Returns the nearest higher-level repo dir from the specified path.

  Copied verbatim from <ChromeOS_root>/chromite/lib/cros_build_lib.py.

  Args:
    path: The path to use. Defaults to cwd.
  Returns:
    a string, the nearest higher-level repo dir from the specified path.
  """
  if path is None:
    path = os.getcwd()
  path = os.path.abspath(path)
  while path != '/':
    repo_dir = os.path.join(path, '.repo')
    if os.path.isdir(repo_dir):
      return repo_dir
    path = os.path.dirname(path)
  return None


def ReinterpretPathForChroot(path):
  """Returns reinterpreted path from outside the chroot for use inside.

  Modified insignificantly from <ChromeOS_root>/chromite/lib/cros_build_lib.py.

  Args:
    path: The path to reinterpret.  Must be in src tree.
  Returns:
    a string, the reinterpreted path from outside the chroot for use inside.
  Raises:
    BundlingError when given a path not in src tree.
  """
  root_path = os.path.join(FindRepoDir(path), '..')
  path_abs_path = os.path.abspath(path)
  root_abs_path = os.path.abspath(root_path)
  # Strip the repository root from the path and strip first /.
  relative_path = path_abs_path.replace(root_abs_path, '')[1:]
  if relative_path == path_abs_path:
    raise cb_constants.BundlingError('Error: '
                        'path is outside your src tree, cannot reinterpret.')
  new_path = os.path.join('/home', os.getenv('USER'), 'trunk', relative_path)
  return new_path


def AskUserConfirmation(msg):
  """Interactively obtain consent from user.

  Args:
    msg: a string describing the permission sought
  Returns:
    a boolean, True when the user gives assent
  """
  logging.info(msg + ' (y/n): ')
  ans = str(raw_input())
  return ans.lower() == 'y'
