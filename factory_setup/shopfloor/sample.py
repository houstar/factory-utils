# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ChromeOS factory shop floor system sample implementation, using CSV input.

This module provides an easy way to setup and use shop floor system. Use Google
Docs or Excel to create a spreadsheet and export as CSV (comma separated
values), with following fields:

  serial_number: The serial number of each device.
  hwid: The HWID string assigned for each serial number.
  ro_vpd_*: Read-only VPD values. Example: ro_vpd_test_data will be converted to
            "test_data" in RO_VPD section.
  rw_vpd_*: Read-writeable VPD values, using same syntax described in ro_vpd_*.

To use this module, run following command in factory_setup folder:
  shopfloor_server.py -m shopfloor.sample.ShopFloor -c PATH_TO_CSV_FILE.csv

You can find a sample CSV file in in:
  factory_setup/test_data/shopfloor/sample.csv
"""

import csv
import logging
import os
import re
import time

import shopfloor


class ShopFloor(shopfloor.ShopFloorBase):
  """Sample shop floor system, using CSV file as input."""
  NAME = "CSV-file based shop floor system"
  VERSION = 1

  def __init__(self, config=None):
    if not (config and os.path.exists(config)):
      raise IOError("You must specify an existing CSV file by -c FILE.")
    logging.info("Parsing %s...", config)
    self.data_store = LoadCsvData(config)
    logging.warn("Loaded %d entries from %s.", len(self.data_store), config)

    # In this sample implementation, we put uploaded reports in a "reports"
    # folder where the input source (csv) file exists.
    self.reports_dir = os.path.join(os.path.realpath(os.path.dirname(config)),
                                    'reports')
    if not os.path.isdir(self.reports_dir):
      os.mkdir(self.reports_dir)

    # Try to touch some files inside directory, to make sure the directory is
    # writable, and everything I/O system is working fine.
    stamp_file = os.path.join(self.reports_dir, ".touch")
    with open(stamp_file, "w") as stamp_handle:
      stamp_handle.write("%s - VERSION %s" % (self.NAME, self.VERSION))
    os.remove(stamp_file)

  def _CheckSerialNumber(self, serial):
    """Checks if serial number is valid, otherwise raise ValueError."""
    if serial in self.data_store:
      return True
    message = "Unknown serial number: %s" % serial
    logging.error(message)
    raise ValueError(message)

  def GetHWID(self, serial):
    self._CheckSerialNumber(serial)
    return self.data_store[serial]['hwid']

  def GetVPD(self, serial):
    self._CheckSerialNumber(serial)
    return self.data_store[serial]['vpd']

  def UploadReport(self, serial, report_blob, report_name=None):
    def is_gzip_blob(blob):
      """Check (not 100% accurate) if input blob is gzipped."""
      GZIP_MAGIC = '\x1f\x8b'
      return blob[:len(GZIP_MAGIC)] == GZIP_MAGIC

    self._CheckSerialNumber(serial)
    if isinstance(report_blob, shopfloor.Binary):
      report_blob = report_blob.data
    if not report_name:
      report_name = ('%s-%s.rpt' % (re.sub('[^a-zA-Z0-9]', '', serial),
                                    time.strftime("%Y%m%d-%H%M%S%z")))
      if is_gzip_blob(report_blob):
        report_name += ".gz"
    report_path = os.path.join(self.reports_dir, report_name)
    with open(report_path, "wb") as report_obj:
      report_obj.write(report_blob)

  def Finalize(self, serial):
    # Finalize is currently not implemented.
    self._CheckSerialNumber(serial)
    logging.warn("Finalized: %s", serial)


def LoadCsvData(filename):
  """Loads a CSV file and returns structured shop floor system data."""
  # Required fields.
  KEY_SERIAL_NUMBER = 'serial_number'
  KEY_HWID = 'hwid'
  # Optional fields.
  PREFIX_RO_VPD = 'ro_vpd_'
  PREFIX_RW_VPD = 'rw_vpd_'
  VPD_PREFIXES = (PREFIX_RO_VPD, PREFIX_RW_VPD)

  REQUIRED_KEYS = (KEY_SERIAL_NUMBER, KEY_HWID)
  OPTIONAL_PREFIXES = VPD_PREFIXES

  def check_field_name(name):
    """Checks if argument is an valid input name."""
    if name in REQUIRED_KEYS:
      return True
    for prefix in OPTIONAL_PREFIXES:
      if name.startswith(prefix):
        return True
    return False

  def build_vpd(source):
    """Builds VPD structure by input source."""
    vpd = {'ro': {}, 'rw': {}}
    for key, value in source.items():
      for prefix in VPD_PREFIXES:
        if not key.startswith(prefix):
          continue
        # Key format: $type_vpd_$name (ex, ro_vpd_serial_number)
        (key_type, _, key_name) = key.split('_', 2)
        if value is None:
          continue
        vpd[key_type][key_name.strip()] = value.strip()
    return vpd

  data = {}
  with open(filename, 'rb') as source:
    reader = csv.DictReader(source)
    row_number = 0
    for row in reader:
      row_number += 1
      if KEY_SERIAL_NUMBER not in row:
        raise ValueError("Missing %s in row %d" % (KEY_SERIAL_NUMBER,
                                                   row_number))
      serial_number = row[KEY_SERIAL_NUMBER].strip()
      hwid = row[KEY_HWID].strip()

      # Checks data validity.
      if serial_number in data:
        raise ValueError("Duplicated %s in row %d: %s" %
                         (KEY_SERIAL_NUMBER, row_number, serial_number))
      if None in row:
        raise ValueError("Extra fields in row %d: %s" %
                         (row_number, ','.join(row[None])))
      for field in row:
        if not check_field_name(field):
          raise ValueError("Invalid field: %s" % field)

      entry = {'hwid': hwid, 'vpd': build_vpd(row)}
      data[serial_number] = entry
  return data
