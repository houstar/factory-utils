# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


"""The package initialization and abstract base class for shop floor systems.

Every implementations should inherit ShopFloorBase and override the member
functions to interact with their real shop floor system.
"""

import os
import xmlrpclib

# In current implementation, we use xmlrpclib.Binary to prepare blobs.
from xmlrpclib import Binary

import factory_update_server

class ShopFloorBase(object):
  NAME = 'ShopFloorBase'
  VERSION = 1
  LATEST_MD5SUM_FILENAME = 'latest.md5sum'

  events_dir = 'events'

  def __init__(self, config=None):
    """Initializes the shop floor system.

    Args:
      config: String of command line parameter "-c" from server invocation.
    """
    pass

  def Ping(self):
    """Always returns true (for client to check if server is working)."""
    return True

  def GetHWID(self, serial):
    """Returns appropriate HWID according to given serial number.

    Args:
      serial: A string of device serial number.

    Returns:
      The associated HWID string.

    Raises:
      ValueError if serial is invalid, or other exceptions defined by individual
      modules. Note this will be converted to xmlrpclib.Fault when being used as
      a XML-RPC server module.
    """
    raise NotImplementedError('GetHWID')

  def GetVPD(self, serial):
    """Returns VPD data to set (in dictionary format).

    Args:
      serial: A string of device serial number.

    Returns:
      VPD data in dict {'ro': dict(), 'rw': dict()}

    Raises:
      ValueError if serial is invalid, or other exceptions defined by individual
      modules. Note this will be converted to xmlrpclib.Fault when being used as
      a XML-RPC server module.
    """
    raise NotImplementedError('GetVPD')

  def UploadReport(self, serial, report_blob, report_name=None):
    """Uploads a report file.

    Args:
      serial: A string of device serial number.
      report_blob: Blob of compressed report to be stored (must be prepared by
          shopfloor.Binary)
      report_name: (Optional) Suggested report file name. This is uslally
          assigned by factory test client programs (ex, gooftool); however
          server implementations still may use other names to store the report.

    Returns:
      True on success.

    Raises:
      ValueError if serial is invalid, or other exceptions defined by individual
      modules. Note this will be converted to xmlrpclib.Fault when being used as
      a XML-RPC server module.
    """
    raise NotImplementedError('UploadReport')

  def Finalize(self, serial):
    """Marks target device (by serial) to be ready for shipment.

    Args:
      serial: A string of device serial number.

    Returns:
      True on success.

    Raises:
      ValueError if serial is invalid, or other exceptions defined by individual
      modules. Note this will be converted to xmlrpclib.Fault when being used as
      a XML-RPC server module.
    """
    raise NotImplementedError('Finalize')

  def GetTestMd5sum(self):
    """Gets the latest md5sum of dynamic test tarball.

    Returns:
      A string of md5sum.  None if no dynamic test tarball is installed.
    """
    if not self.update_dir:
      return None

    md5file = os.path.join(self.update_dir,
                           factory_update_server.FACTORY_DIR,
                           self.LATEST_MD5SUM_FILENAME)
    if not os.path.isfile(md5file):
      return None
    with open(md5file, 'r') as f:
      return f.readline().strip()

  def GetUpdatePort(self):
    """Returns the port to use for rsync updates.

    Returns:
      The port, or None if there is no update server available.
    """
    return self.update_port

  def UploadEvent(self, log_name, chunk):
    """Uploads a chunk of events.

    Args:
      log_name: A string of the event log filename. Event logging module creates
          event files with an unique identifier (uuid) as part of the filename.
      chunk: A string containing one or more events. Events are in YAML format
          and separated by a "---" as specified by YAML. A chunk contains one or
          more events with separator.

    Returns:
      True on success.

    Raises:
      IOError if unable to save the chunk of events.
    """
    if not os.path.exists(self.events_dir):
      os.makedirs(self.events_dir)

    if isinstance(chunk, Binary):
      chunk = chunk.data

    log_file = os.path.join(self.events_dir, log_name)
    with open(log_file, 'a') as f:
      f.write(chunk)
    return True
