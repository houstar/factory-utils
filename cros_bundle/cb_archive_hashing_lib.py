#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module contains hashing and compression methods."""

import hashlib
import logging
import os
import zipfile

from cb_util import RunCommand


def CheckMd5(filename, md5filename):
  """Checks the MD5 checksum of file against provided baseline .md5

  Args:
    filename: name of file to check MD5 checksum
    md5filename: name of file with reference MD5 checksum
  Returns:
    a boolean, True when the MD5 checksums agree
  """
  try:
    hasher = hashlib.md5()
    with open(filename) as check_file:
      with open(md5filename) as golden_file:
        for chunk in iter(lambda: check_file.read(128*hasher.block_size), ''):
          hasher.update(chunk)
        md5_contents = golden_file.read()
        if md5_contents:
          golden_digest_and_more = md5_contents.split(' ')
          if golden_digest_and_more:
            return golden_digest_and_more[0] == hasher.hexdigest()
        logging.warning('MD5 checksum match failed for %s', filename)
        return False
  except IOError:
    logging.warning('MD5 hasher read failed for %s', filename)
    return False


def MakeMd5(filename, md5filename):
  """Creates an MD5 checksum file from a provided file.

  Assuming directory of destination file is writable.

  Args:
    filename: absolute path name of file to hash
    md5filename: absolute path name of MD5 file to create
  Returns:
    a boolean, True when md5checksum file is successfully created
  """
  try:
    with open(filename, 'r') as read_file:
      with open(md5filename, 'w') as hash_file:
        hasher = hashlib.md5()
        for chunk in iter(lambda: read_file.read(128*hasher.block_size), ''):
          hasher.update(chunk)
        hash_file.write(hasher.hexdigest())
        return True
  except IOError:
    logging.error('Failed to compute md5 checksum for file %s.',
                  filename)
    return False


def GenerateMd5(filename):
  """Generates an MD5 checksum from a provided file.

  Args:
    filename: absolute path name of file to hash
  Returns:
    a string, the hexdigest form of the MD5 checksum, empty on failure
  """
  try:
    with open(filename, 'r') as read_file:
      hasher = hashlib.md5()
      for chunk in iter(lambda: read_file.read(128*hasher.block_size), ''):
        hasher.update(chunk)
      return hasher.hexdigest()
  except IOError:
    logging.error('Failed to compute md5 checksum for file %s.',
                  filename)
    return ''


def ZipExtract(zipname, filename, path=os.getcwd()):
  """Extract a file from a zip archive.

  Assuming path, if provided, exists and is writable.

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
    logging.warning('Could not find %s to extract from %s.',
                    (filename, zipname))
    return False


def MakeTar(target_dir, destination_dir, name=None):
  """Creates a tar.bz2 archive of a target directory.

  Args:
    target_dir: absolute path to directory with contents to tar
    destination_dir: directory in which to put tar file
    name: filename without directory path of tar file to create
  Returns:
    a string, the basename of the tar created or None on failure
  """
  if not (target_dir and os.path.isdir(target_dir)):
    logging.error('Tar target directory does not exist.')
    return None
  if not (destination_dir and os.path.isdir(destination_dir)):
    logging.error('Tar destination directory does not exist.')
    return None
  if not os.access(destination_dir, os.W_OK):
    logging.error('Tar destination directory %s not writable.',
                  destination_dir)
    return None
  cmd_result = RunCommand(['which', 'pbzip2'], redirect_stdout=True)
  output_string = cmd_result.output
  if not output_string:
    logging.error('\nMissing pbzip2. Please run sudo apt-get install pbzip2\n')
    return None
  folder_name = os.path.basename(target_dir)
  if not name:
    name = folder_name + '.tar.bz2'
  # use pbzip2 for speed
  name = os.path.join(destination_dir, name)
  RunCommand(['tar', '-c', '-I', 'pbzip2', folder_name, '-f', name],
             cwd=os.path.dirname(target_dir))
  return name
