#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module contains methods for interacting with online resources."""

import contextlib
import formatter
import logging
import os
import re
import urllib

import cb_constants
import cb_util_lib

from htmllib import HTMLParser

from cb_constants import BundlingError


class UrlLister(HTMLParser):

  """List all hyperlinks found on an html page.

  It contains the following fields:
  - urls: list of urls found

  The href attribute of all anchor tags will be stored in urls, so if the page
  has relative links then for those urls stored they will be relative links.
  Example:
  <a href="http://google.com/">Google</a> -> "http://google.com"
  <a href="my_filename_here.zip">My file!</a> -> "my_filename_here.zip"

  Modified from http://diveintopython.org/html_processing/extracting_data.html
  """

  def __init__(self, given_formatter):
    HTMLParser.__init__(self, given_formatter)
    self.urls = []

  def reset(self):
    """Reset the parser to clean state."""
    HTMLParser.reset(self)
    self.urls = []

  def start_a(self, attrs):
    """Add urls found to list of urls.

    Args:
      attrs: attributes of the anchor tag
    """
    href = [v for k, v in attrs if k == 'href']
    if href:
      self.urls.extend(href)


class NameResolutionError(Exception):
  """Error to be thrown upon URL naming resolution failure."""
  def __init__(self, reason):
    Exception.__init__(self, reason)
    logging.debug('Name resolution failed on:\n' + reason + '\n')


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
  try:
    usock = urllib.urlopen(url)
  except IOError:
    logging.warning('Could not open %s.', url)
    return None
  htmlformatter = formatter.NullFormatter()
  parser = UrlLister(htmlformatter)
  parser.feed(usock.read())
  usock.close()
  parser.close()
  link = MatchUrl(parser.urls, pattern)
  return os.path.join(url, link)


def MatchUrl(url_list, pattern):
  """Return a URL from a list given a pattern to match.

  If more than one URL is found to match, the first will be returned.
  Any other matches will be logged as a warning.

  Args:
    url_list: a list of URLs to match against
    pattern: a string, a regex pattern to match
  Returns:
    a string, a matching URL, or None if no matching URL found
  """
  pat = re.compile(pattern)
  if url_list:
    matches = [u for u in url_list if pat.search(u)]
    if matches:
      if len(matches) > 1:
        logging.warning('More than one resource matching %s found.', pattern)
        for match in matches[1:]:
          logging.warning('Additional match %s found and ignored.', match)
      return matches[0]
  return None


def Download(url):
  """Copy the contents of a file from a given URL to a local file.

  Local file stored in a tmp dir specified in "cb_constants.TMPDIR" variable.
  If local file exists, it will be overwritten by default.

  Modified from code.activestate.com/recipes/496685-downloading-a-file-from-
  the-web/

  Args:
    url: online location of file to download
  Returns:
    a boolean, True only when file is fully downloaded
  """
  try:
    with contextlib.closing(urllib.urlopen(url)) as web_file:
      local_file_name = os.path.join(cb_constants.TMPDIR, url.split('/')[-1])
      with open(local_file_name, 'w') as local_file:
        local_file.write(web_file.read())
        return True
  except IOError:
    logging.warning('Could not open %s or writing local file failed.', url)
    return False


def DetermineThenDownloadCheckMd5(url, pattern, path, desc):
  """Determine exact url then download the resource and check MD5.

  Args:
    url: html page with a relative link matching the pattern
    pattern: a string, a regex pattern to match within links present on page
    path: absolute path of directory to put resource
    desc: a short string description of the resource to fetch
  Returns:
    a string, the absolute path to the resource, None on failure
  Raises:
    BundlingError when resources cannot be fetched or download integrity fails.
  """
  url = DetermineUrl(url, pattern)
  if not url:
    raise NameResolutionError(desc + ' exact URL could not be determined.')
  return DownloadCheckMd5(url, path, desc)


def CheckResourceExistsWithMd5(filename, md5filename):
  """Check if a resource exists in the local file system with a good MD5.

  Args:
    filename: name of file to check for
    md5filename: name of file containing golden MD5 checksum
  Returns:
    a boolean, True when the file exists with good MD5
  """
  return (os.path.exists(filename) and
          os.path.exists(md5filename) and
          cb_util_lib.CheckMd5(filename, md5filename))


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
  Raises:
    BundlingError when resources cannot be fetched or download integrity fails.
  """
  name = os.path.join(path, url.split('/')[-1])
  if CheckResourceExistsWithMd5(name, name + '.md5'):
    logging.info('Resource %s already exists with good MD5, skipping fetch.',
                 name)
  else:
    logging.info('Downloading ' + url)
    if not Download(url):
      raise BundlingError(desc + ' could not be fetched.')
    if not Download(url + '.md5'):
      raise BundlingError(desc + ' MD5 could not be fetched.')
    if not cb_util_lib.CheckMd5(name, name + '.md5'):
      raise BundlingError(desc + ' MD5 checksum does not match.')
    logging.debug('MD5 checksum match succeeded for %s', name)
  return name
