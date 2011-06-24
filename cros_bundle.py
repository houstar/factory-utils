#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This script repackages ChromeOS images into a factory bundle.

This script runs outside the chroot environment in the
<chromeos_root>/src/scripts directory.
Assuming sufficient disk space in /usr partition, at least 20 GB free.

Usage: python cros_bundle.py --board x86-alex --release 0.11.257.90/stable/mp
       --factory 0.11.257.90/stable --shim 0.11.241.28/dev/mp
       --recovery 0.11.257.90/stable/mp
"""

import datetime
import hashlib
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib
import zipfile

from optparse import OptionParser
from sgmllib import SGMLParser

_TMPDIR = '/usr/local/google/cros_bundle/tmp'
_PREFIX = 'http://chromeos-images/chromeos-official'
_EC_NAME = 'ec.bin'
_BIOS_NAME = 'bios.bin'
_MOUNT_POINT = '/tmp/m'


class UrlLister(SGMLParser):

  """List all hyperlinks found on an html page.

  It contains the following fields:
  - urls: list of urls found

  The href attribute of all anchor tags will be stored in urls, so if the page
  has relative links then for those urls stored they will be relative links.
  Example:
  <a href="http://google.com/">Google</a> -> "http://google.com"
  <a href="my_filename_here.zip">My file!</a> -> "my_filename_here.zip"

  Borrowed from http://diveintopython.org/html_processing/extracting_data.html
  """

  def __init__(self):
    SGMLParser.__init__(self)
    self.urls = []

  def reset(self):
    """Reset the parser to clean state."""
    SGMLParser.reset(self)
    self.urls = []

  def start_a(self, attrs):
    """Add urls found to list of urls.

    Args:
      attrs: attributes of the anchor tag
    """
    href = [v for k, v in attrs if k == 'href']
    if href:
      self.urls.extend(href)


class BundlingError(Exception):
  """Common exception for bundling process errors."""
  def __init__(self, reason):
    Exception.__init__(self, reason)
    logging.error('Script exiting due to:\n' + reason + '\n')


class CommandResult(object):
  """An object to store various attributes of a child process.

  Borrowed from <chromeos_root>/chromite/lib/cros_build_lib.py
  """
  def __init__(self):
    self.cmd = None
    self.error = None
    self.output = None
    self.returncode = None


def RunCommand(cmd, redirect_stdout=False, redirect_stderr=False):
  """Runs a command using subprocess module Popen.

  Blocks until command returns.
  Modeled on RunCommand from <chromeos_root>/chromite/lib/cros_build_lib.py

  Args:
    cmd: a list of arguments to Popen
    redirect_stdout: a boolean, True when subprocess output should be returned
  Returns:
    a CommandResult object.
  Throws:
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

  proc = subprocess.Popen(cmd, stdout=stdout, stderr=stderr)
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


def CheckMd5(filename):
  """Checks the MD5 checksum of file against provided baseline .md5

  Assuming baseline .md5 is stored in same directory as filename.md5

  Args:
    filename: name of file to check MD5 checksum
  Returns:
    a boolean, True when the MD5 checksums agree
  """
  try:
    hasher = hashlib.md5()
    file_to_check = open(filename)
    for chunk in iter(lambda: file_to_check.read(128*hasher.block_size), ''):
      hasher.update(chunk)
    golden_file = open(filename + '.md5')
    md5_contents = golden_file.read()
    if len(md5_contents):
      golden_digest_and_more = md5_contents.split(' ')
      if len(golden_digest_and_more):
        logging.debug('MD5 checksum match succeeded for %s' % filename)
        return golden_digest_and_more[0] == hasher.hexdigest()
    logging.warning('MD5 checksum match failed for %s' % filename)
    return False
  except IOError:
    logging.warning('MD5 checksum match failed for %s' % filename)
    return False
  finally:
    if file_to_check:
      file_to_check.close()
    if golden_file:
      golden_file.close()


def DetermineUrl(url, pattern):
  """Return an exact URL linked from a page given a pattern to match.

  Assuming links are relative from the given page.
  If more than one URL is found to match, the first will be returned.
  Any other matches will be logged as a warning.

  Args:
    url: html page with a relative link matching the pattern
    pattern: a string, a regex pattern to match within links present on page
  Returns:
    a string, an exact URL, or None if URL not present or link not found
  """
  pat = re.compile(pattern)
  try:
    usock = urllib.urlopen(url)
  except IOError:
    logging.warning('Could not open %s.' % url)
    return None
  parser = UrlLister()
  parser.feed(usock.read())
  usock.close()
  parser.close()
  if len(parser.urls):
    matches = [u for u in parser.urls if pat.search(u)]
    if len(matches):
      if len(matches) > 1:
        logging.warning('More than one resource matching %s found.' % pattern)
        for match in matches[1:]:
          logging.warning('Additional match %s found.' % match)
      return '/'.join([url, matches[0]])
  return None


def Download(url):
  """Copy the contents of a file from a given URL to a local file.

  Local file is stored in a tmp directory specified in "_TMPDIR" variable.
  If local file exists, it will be overwritten by default.

  Modified from code.activestate.com/recipes/496685-downloading-a-file-from-
  the-web/

  Args:
    url: online location of file to download
  Returns:
    a boolean, True only when file is fully downloaded
  """
  try:
    web_file = urllib.urlopen(url)
    local_file = open(os.path.join(_TMPDIR, url.split('/')[-1]), 'w')
    local_file.write(web_file.read())
    return True
  except IOError:
    logging.warning('Could not open %s or writing %s failed.' %
                    (url, local_file))
    return False
  finally:
    if web_file:
      web_file.close()
    if local_file:
      local_file.close()


def ZipExtract(zipname, filename, path=os.getcwd()):
  """Extract a file from a zip archive.

  Args:
    zipname: name of the zip archive
    filename: name of the file to extract
    path: optional name of directory to extract file to
  Returns:
    a boolean, True only when the file is successfully extracted
  """
  try:
    zpf = zipfile.ZipFile(zipname)
    zpf.extract(filename, path)
    zpf.close()
    return True
  except KeyError:
    logging.warning('Could not find %s to extract from %s.' %
                    (filename, zipname))
    return False


def MakeTar(target_dir, destination_dir, name=None):
  """Creates a tar.bz2 archive of a target directory.

  Args:
    target_dir: directory with contents to tar
    destination_dir: directory in which to put tar file
    name: filename without directory path of tar file to create
  Returns:
    a boolean, True when tar file is successfully created
  """
  if not (target_dir and os.path.isdir(target_dir)):
    logging.error('Tar target directory does not exist.')
    return False
  if not (destination_dir and os.path.isdir(destination_dir)):
    logging.error('Tar destination directory does not exist.')
    return False
  if not os.access(destination_dir, os.W_OK):
    logging.error('Tar destination directory %s not writable.',
                  destination_dir)
    return False
  folder_name = target_dir.split(os.sep)[-1]
  if not name:
    name = folder_name + '.tar.bz2'
  tar = tarfile.open(os.path.join(destination_dir, name), mode='w:bz2')
  tar.add(target_dir, arcname=folder_name)
  tar.close()
  return True


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
    mount_point: directory to mount SSD image, defaults to _MOUNT_POINT
  Returns:
     a boolean, True when the conditions checked are all satisfied
  """
  # TODO(benwin) refactor so this check comes at the beginning of the script
  res = True
  if not re.search('/src/scripts$', os.getcwd()):
    logging.error('Please run this script from the src/scripts directory.')
    res = False
  cmd_result = RunCommand(['which', 'uudecode'], redirect_stdout=True)
  output_string = cmd_result.output
  if not output_string:
    logging.error('Missing uudecode. Please run sudo apt-get install '
                  'sharutils')
    res = False
  if (not os.path.isfile(image_name) or
      not re.search('.*ssd.*[.]bin$', image_name)) :
    logging.error('Bad SSD image name given : %s' % image_name)
    res = False
  if not os.path.isdir(firmware_dest):
    logging.error('Firmware destination directory %s does not exist!' %
                  firmware_dest)
    res = False
  if not os.access(firmware_dest, os.W_OK):
    logging.error('Firmware destination directory %s not writable.' %
                  firmware_dest)
    res = False
  if os.path.isdir(mount_point) and os.listdir(mount_point):
    logging.error('Mount point %s is not emtpy!' % mount_point)
    res = False
  return res


def ListFirmware(image_name, cros_fw):
  """Get list of strings representing contents of firmware.

  Args:
    image_name: absolute file path to SSD release image binary
    cros_fw: absolute path of firmware extraction script
  Returns:
    a tuple of strings (ec_name, bios_name)
  Throws:
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
  if _EC_NAME not in firmfiles:
    raise BundlingError('Necessary file ec.bin missing from %s.' % cros_fw)
  # TODO(benwin) add additional branching for h2c binary
  if _BIOS_NAME not in firmfiles:
    raise BundlingError('Necessary file bios.bin missing from %s.' % cros_fw)
  ec_name = _EC_NAME
  ec_searches = [re.search('EC image:.*', line) for line in lines]
  ec_matches = [match.group() for match in ec_searches if match]
  if len(ec_matches):
    ec_name = ec_matches[0].split('/')[-1]
  else:
    logging.warning('Proper renaming of ec.bin firmware failed.')
  bios_name = _BIOS_NAME
  bios_searches = [re.search('BIOS image:.*', line) for line in lines]
  bios_matches = [match.group() for match in bios_searches if match]
  if len(bios_matches):
    bios_name = bios_matches[0].split('/')[-1]
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
    logging.error('Necessary firmware extraction script %s missing.' % cros_fw)
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
    mount_point: directory to mount SSD image, defaults to _MOUNT_POINT
  Returns:
    a boolean, True when the firmware has been successfully extracted
  Throws:
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
                '--from=' + _TMPDIR, '--image=' + image,
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
    shutil.copy(os.path.join(firmdir, _EC_NAME),
                os.path.join(firmware_dest, ec_name))
    shutil.copy(os.path.join(firmdir, _BIOS_NAME),
                os.path.join(firmware_dest, bios_name))
    shutil.copy(cros_fw, firmware_dest)
  finally:
    RunCommand(['./mount_gpt_image.sh', '--unmount'])
  if not CheckMd5(os.path.join(_TMPDIR, image_name)):
    logging.error('SSD image MD5 checksum did not match, image was corrupted!')
    return False
  return True


def CheckBundleInputs(image_names, fsi, firmware):
  """Checks the input for making a factory bundle.

  In particular:
  - checks for conflicting input flags no_firmware and fsi
  - binary image names correctly passed by image fetch
  - binary image names point to existing files

  Args:
    image_names: a dict with values of absolute file paths to images for keys:
      'ssd': release image
      'recovery': recovery image
      'factorybin': factory binary
    fsi: a boolean, True when processing for a Final Shipping Image
    firmware: a boolean, True when script should extract firmware
  Returns:
    a tuple (ssd_name, rec_name, fac_name) on failure
  Throws:
    BundlingError when a check fails.
  """
  if not firmware and not fsi:
    raise BundlingError('Can only skip firmware extraction for '
                        'final shipping image.')
  ssd_name = image_names.get('ssd', None)
  rec_name = image_names.get('recovery', None)
  fac_name = image_names.get('factorybin', None)
  msg = []
  if ssd_name:
    if not os.path.isfile(ssd_name):
      msg.append('SSD image does not exist.')
  else:
    msg.append('Bundling method does not receive ssd image name.')
  if rec_name:
    if not os.path.isfile(rec_name):
      msg.append('Recovery image does not exist.')
  else:
    msg.append('Bundling method does not receive recovery image name.')
  if fac_name:
    if not os.path.isfile(fac_name):
      msg.append('Factory image does not exist.')
  else:
    msg.append('Bundling method does not receive factory image name.')
  if msg:
    raise BundlingError('\n'.join(msg))
  return (ssd_name, rec_name, fac_name)


def MakeFactoryBundle(image_names, fsi, firmware, version, mount_point,
                      bundle_dir, tar_dir, del_ok=False):
  """Produces a factory bundle from the downloaded images.

  Requires current directory to be <ChromeOS_root>/src/scripts.
  Requires sudoer password entry to mount SSD image.
  Bundle is named with input version as well as the current date.
  Forces exit if any bundle components exist, use flags to override.

  Args:
    image_names: a dict with values of absolute file paths to images for keys:
      'ssd': release image
      'recovery': recovery image
      'factorybin': factory binary
    fsi: a boolean, True when processing for a Final Shipping Image
    firmware: a boolean, True when script should extract firmware
    version: key and version for bundle naming, e.g. mp9x
    bundle_dir: destination directory for factory bundle files
    tar_dir: destination directory for factory bundle tar file
    del_ok: a boolean, True when any existing bundle files can be deleted
  Throws:
    BundlingError on bad input, inability to write, or firmware extract fail.
  """
  (ssd_name, rec_name, fac_name) = CheckBundleInputs(image_names, fsi,
                                                     firmware)
  today = datetime.date.today().strftime('%Y_%m_%d')
  if bundle_dir:
    if not os.path.isdir(bundle_dir):
      raise BundlingError('Provided directory %s does not exist.' % bundle_dir)
    if not os.access(bundle_dir, os.W_OK):
      raise BundlingError('Provided directory %s not writable.' % bundle_dir)
  else:
    items = ['factory', 'bundle', today]
    if version:
      items.insert(2, version)
    bundle_dir = os.path.join(_TMPDIR, '_'.join(items))
  if os.path.exists(bundle_dir):
    if del_ok:
      shutil.rmtree(bundle_dir)
    else:
      raise BundlingError('Directory %s already exists. Use -f to overwrite.' %
              bundle_dir)
  os.mkdir(bundle_dir)
  if not(tar_dir and os.path.isdir(tar_dir)):
      logging.warning('Provided directory %s does not exist, using %s',
                      tar_dir, _TMPDIR)
      tar_dir = _TMPDIR
  else:
    tar_dir = _TMPDIR
  if firmware:
    firmware_dest = os.path.join(bundle_dir, 'firmware')
    if os.path.exists(firmware_dest):
      if del_ok:
        shutil.rmtree(firmware_dest)
      else:
        raise BundlingError('Directory %s exists. Use -f to overwrite.' %
                firmware_dest)
    os.mkdir(firmware_dest)
    if ExtractFirmware(ssd_name, firmware_dest, mount_point):
      logging.info('Successfully extracted firmware to %s' % firmware_dest)
    else:
      raise BundlingError('Failed to extract firmware from SSD image %s.' %
                          ssd_name)
  shutil.copy(ssd_name, bundle_dir)
  shutil.copy(rec_name, bundle_dir)
  if not fsi:
    # TODO(benwin) copy install shim into bundle_dir
    shutil.copy(fac_name, bundle_dir)
  logging.info('Completed copying factory bundle files to %s' % bundle_dir)
  if not MakeTar(bundle_dir, tar_dir):
    raise BundlingError('Failed to create tar file of bundle directory.')
  logging.info('Completed creating factory bundle tar file in %s.' % _TMPDIR)


def GetReleaseName(board, release):
  """Determines release page URL and naming pattern of desired release image.

  Args:
    board: target board
    release: release candidate version, channel, and signing key
  Returns:
    rel_url: a string, the release page URL
    rel_pat: a string, the naming pattern for the release image
  """
  rel_no, rel_ch, rel_key = release.split('/')
  rel_ch = rel_ch + '-channel'
  rel_url = os.path.join(_PREFIX, rel_ch, board, rel_no)
  rel_pat = '_'.join(['chromeos', rel_no, board, 'ssd', rel_ch,
             rel_key + '.*[.]bin$'])
  return (rel_url, rel_pat)


def GetFactoryName(board, factory):
  """Determines release page URL and naming pattern of desired factory image.

  Args:
    board: target board
    factory: factory version and channel
  Returns:
    fac_url: a string, the release page URL
    fac_pat: a string, the naming pattern for the factory image
  """
  fac_no, fac_ch = factory.split('/')
  fac_ch = fac_ch + '-channel'
  fac_url = os.path.join(_PREFIX, fac_ch, board, fac_no)
  fac_pat = ''.join(['ChromeOS-factory-', fac_no, '.*', board, '[.]zip$'])
  return (fac_url, fac_pat)


def GetRecoveryName(board, recovery):
  """Determines release page URL and naming pattern of desired recovery image.

  Args:
    board: target board
    recovery: recovery version, channel, and signing key
  Returns:
    rec_url: a string, the release page URL
    rec_pat: a string, the naming pattern for the recovery image
  """
  rec_no, rec_ch, rec_key = recovery.split('/')
  rec_ch = rec_ch + '-channel'
  rec_url = os.path.join(_PREFIX, rec_ch, board, rec_no)
  rec_pat = '_'.join(['chromeos', rec_no, board, 'recovery', rec_ch,
             rec_key + '.*[.]bin$'])
  return (rec_url, rec_pat)


def DownloadCheckMd5(url, path, desc):
  """Download a resource and check the MD5 checksum.

  Assuming a golden md5 is available from <resource_url>.md5
  Also checks if the resource is already locally present with an MD5 to check.

  Args:
    url: url at which resource can be downloaded
    path: absolute path of directory to put resource
    desc: a short string description of the resource to fetch
  Returns:
    a string, the absolute path to the resource, None on failure
  Throws:
    BundlingError when resources cannot be fetched or download integrity fails.
  """
  name = os.path.join(path, url.split('/')[-1])
  if (os.path.exists(name) and
      os.path.exists(name + '.md5') and
      CheckMd5(name)):
    logging.info('Resource %s already exists with good MD5, skipping fetch.' %
                 name)
  else:
    logging.info('Downloading ' + url)
    if not Download(url):
      raise BundlingError(desc + ' could not be fetched.')
    if not Download(url + '.md5'):
      raise BundlingError(desc + ' MD5 could not be fetched.')
    if not CheckMd5(name):
      raise BundlingError(desc + ' MD5 checksum does not match.')
  return name


def FetchImages(board, release, factory, recovery, fsi):
  """Fetches images for factory bundle specified by args input

  Args:
    board: target board
    release: release candidate version, channel, and signing key
    factory: factory image version and channel
    recovery: recovery image version, channel, and signing key
    fsi: a boolean, True when processing for Final Shipping Image
  Returns:
    a dict, values are absolute file paths for keys:
      'ssd': release image
      'recovery': recovery image
      'factorybin': factory binary
  Throws:
    BundlingError when resources cannot be fetched.
  """
  # TODO(benwin) refactor this function, it is too long
  rel_url, rel_pat = GetReleaseName(board, release)
  fac_url, fac_pat = GetFactoryName(board, factory)
  rec_url, rec_pat = GetRecoveryName(board, recovery)
  # Determine urls
  rel_url = DetermineUrl(rel_url, rel_pat)
  if not rel_url:
    raise BundlingError('Release image exact URL could not be determined.')
  rec_url = DetermineUrl(rec_url, rec_pat)
  if not rec_url:
    raise BundlingError('Recovery image exact URL could not be determined.')
  if not fsi:
    fac_url = DetermineUrl(fac_url, fac_pat)
    if not fac_url:
      raise BundlingError('Factory image exact URL could not be determined.')
  # Release
  rel_name = DownloadCheckMd5(rel_url, _TMPDIR, 'Release image')
  if not fsi:
    # Factory
    fac_name = os.path.join(_TMPDIR, fac_url.split('/')[-1])
    if os.path.exists(fac_name):
      logging.info('Resource %s already exists, skipping fetch.' %
                   fac_name)
    else:
      logging.info('Downloading ' + fac_url)
      if not Download(fac_url):
        raise BundlingError('Factory image could not be fetched.')
    factorybin = os.path.join('factory_test', 'chromiumos_factory_image.bin')
    absfactorybin = os.path.join(_TMPDIR, factorybin)
    if os.path.exists(absfactorybin):
      logging.info('Resource %s already present, skipping zip extraction.' %
                   absfactorybin)
    else:
      logging.info('Extracting factory image binary')
      if not ZipExtract(fac_name,
                        factorybin,
                        path=_TMPDIR):
        raise BundlingError('Could not find chromiumos_factory_image.bin '
                            'in factory image.')
  # Recovery
  rec_name = DownloadCheckMd5(rec_url, _TMPDIR, 'Recovery image')
  # TODO(benwin) add naming, download, and check for factory install shim
  image_names = dict(ssd=rel_name, recovery=rec_name, factorybin=absfactorybin)
  return image_names


def main():
  """Main method to initiate fetching and processing of bundle components.

  Throws:
    BundlingError when image fetch or bundle processing fail.
  """
  parser = OptionParser()
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
                    help='destination directory for factory bundle files')
  parser.add_option('--tar_dir', action='store', dest='tar_dir',
                    help='destination directory for factory bundle tar')
  (options, args) = parser.parse_args()
  if IsInsideChroot():
    logging.error('Please run this script outside the chroot environment.')
    exit()
  if options.clean:
    if os.path.exists(_TMPDIR):
      shutil.rmtree(_TMPDIR)
      exit()
  image_names =  FetchImages(options.board, options.release, options.factory,
                             options.recovery, options.fsi)
  if not options.mount_point:
    mount_point = _MOUNT_POINT
  MakeFactoryBundle(image_names, options.fsi, options.fw, options.version,
                    mount_point, options.bundle_dir, options.tar_dir,
                    options.force)


if __name__ == "__main__":
  if not os.path.exists(_TMPDIR):
    os.makedirs(_TMPDIR)
  logging.basicConfig(level=logging.DEBUG,
                      filename=os.path.join(_TMPDIR, 'cros_bundle.log'))
  console = logging.StreamHandler()
  console.setLevel(logging.DEBUG)
  logging.getLogger('').addHandler(console)
  main()
