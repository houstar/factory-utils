#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This script repackages ChromeOS images into a factory bundle.

This script runs outside the chroot environment in a directory where the
factory bundle will be placed.

Usage: python cros_bundle.py --board x86-alex --release 0.11.257.90/stable/mp
       --factory 0.11.257.90/stable --shim 0.11.241.28/dev/mp
       --recovery 0.11.257.90/stable/mp
"""

import hashlib
import logging
import os
import re
import urllib
import zipfile

from optparse import OptionParser
from sgmllib import SGMLParser

_TMPDIR = '/tmp/cros_bundle'
_PREFIX = 'http://chromeos-images/chromeos-official'


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


def FetchImages(board, release, factory, recovery, fsi):
  """Fetches images for factory bundle specified by args input

  Args:
    board: target board
    release: release candidate version, channel, and signing key
    factory: factory image version and channel
    recovery: recovery image version, channel, and signing key
    fsi: a boolean, True when processing for Final Shipping Image
  """
  rel_url, rel_pat = GetReleaseName(board, release)
  fac_url, fac_pat = GetFactoryName(board, factory)
  rec_url, rec_pat = GetRecoveryName(board, recovery)
  # Determine urls
  rel_url = DetermineUrl(rel_url, rel_pat)
  if not rel_url:
    ExitNow('Release image exact URL could not be determined.')
  rec_url = DetermineUrl(rec_url, rec_pat)
  if not rec_url:
    ExitNow('Recovery image exact URL could not be determined.')
  if not fsi:
    fac_url = DetermineUrl(fac_url, fac_pat)
    if not fac_url:
      ExitNow('Factory image exact URL could not be determined.')
  # Release
  logging.info('Downloading ' + rel_url)
  # TODO(benwin) save time by checking if file exists and has good MD5
  if not Download(rel_url):
    ExitNow('Release image could not be fetched.')
  if not Download(rel_url + '.md5'):
    ExitNow('Release image MD5 could not be fetched.')
  if not CheckMd5(os.path.join(_TMPDIR, rel_url.split('/')[-1])):
    ExitNow('Release image MD5 checksum did not match.')
  # TODO(benwin) Refactor Download file, Download MD5, Check MD5
  if not fsi:
    # Factory
    logging.info('Downloading ' + fac_url)
    if not Download(fac_url):
      ExitNow('Factory image could not be fetched.')
    logging.info('Extracting factory image binary')
    filename = os.path.join('factory_test', 'chromiumos_factory_image.bin')
    if not ZipExtract(os.path.join(_TMPDIR, fac_url.split('/')[-1]),
                      filename,
                      path=_TMPDIR):
      ExitNow('Could not find chromiumos_factory_image.bin in factory image.')
  # Recovery
  logging.info('Downloading ' + rec_url)
  if not Download(rec_url):
    ExitNow('Recovery image could not be fetched.')
  if not Download(rec_url + '.md5'):
    ExitNow('Recovery image MD5 could not be fetched.')
  if not CheckMd5(os.path.join(_TMPDIR, rec_url.split('/')[-1])):
    ExitNow('Recovery image MD5 checksum did not match.')
  # TODO(benwin) add naming, download, and check for factory install shim


def ExitNow(reason):
  """Common handling for when the script should exit prematurely.

  Args:
    reason: why the script is exiting
  """
  logging.error('Script exiting due to:\n' + reason + '\n')
  exit()


def main():
  """Main method to initiate fetching and processing of bundle components."""
  parser = OptionParser()
  parser.add_option('-b', '--board', action='store', type='string',
                    dest='board', help='target board')
  parser.add_option('-r', '--release', action='store', type='string',
                    dest='release', help='release candidate version')
  parser.add_option('-f', '--factory', action='store', type='string',
                    dest='factory', help='factory image version')
  parser.add_option('-s', '--shim', action='store', type='string',
                    dest='shim', help='install shim version')
  parser.add_option('-c', '--recovery', action='store', type='string',
                    dest='recovery', help='recovery image version')
  parser.add_option('--fsi', action='store_true', dest='fsi',
                    help='use to process for final shipping image')
  (options, args) = parser.parse_args()
  FetchImages(options.board, options.release, options.factory,
              options.recovery, options.fsi)


if __name__ == "__main__":
  if not os.path.exists(_TMPDIR):
    os.mkdir(_TMPDIR)
  logging.basicConfig(level=logging.DEBUG,
                      filename=os.path.join(_TMPDIR, 'cros_bundle.log'))
  console = logging.StreamHandler()
  console.setLevel(logging.DEBUG)
  logging.getLogger('').addHandler(console)
  main()
