# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


"""The package initialization and abstract base class for shop floor systems.

Every implementations should inherit ShopFloorBase and override the member
functions to interact with their real shop floor system.
"""


import xmlrpclib

# In current implementation, we use xmlrpclib.Binary to prepare blobs.
from xmlrpclib import Binary


class ShopFloorBase(object):

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
    raise NotImplementedError('GetTestMd5sum')
