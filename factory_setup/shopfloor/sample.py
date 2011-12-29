# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


'''
This module provides a sample implementation of factory shop floor system.

To use this module, run:
  python shopfloor_server.py -m shopfloor.sample.SampleShopfloor

To create your own module, start with "template.py".
'''


import copy
import logging
import os
import shelve
import time

import shopfloor


class SampleShopFloor(shopfloor.ShopFloorBase):
  '''The sample implementation for factory shop floor system.

  This sample system stores everything in a Python dict (and serialized to
  DEFAULT_DATA_STORE_FILE or the file assigned by config param),
  initialized by function _CreateSampleDatabase.
  '''
  NAME = 'Sample Implementation (do NOT use for production)'
  VERSION = 1

  DEFAULT_DATA_STORE_FILE = '/tmp/cros_shopfloor.db'

  def __init__(self, config=None):
    '''Initializes the sample shop floor server.

    Args:
      config: File path for data store file name.
    '''
    logging.info('Shop floor system started.')
    self.data_file = config or self.DEFAULT_DATA_STORE_FILE
    self.data_store = None
    try:
      self.data_store = shelve.open(self.data_file, protocol=2)
    except:
      logging.critical('Invalid data store file: %s', self.data_file)
      os.unlink(self.data_file)
      self.data_store = shelve.open(self.data_file, protocol=2)

    if (('VERSION' not in self.data_store) or
        self.data_store['VERSION'] != self.VERSION):
      logging.info('Re-creating sample data store.')
      self.data_store.clear()
      self.data_store.update(_CreateSampleDatabase())
      self.data_store['VERSION'] = self.VERSION
      self._Flush()

  def _Flush(self):
    '''Updates data store into persistent storage.'''
    try:
      self.data_store.sync()
    except:
      logging.critical('Failed to flush data store file: %s', self.data_file)

  def _AppendStatus(self, serial, msg):
    '''Appends one message to status log.'''
    self.data_store[serial]['status'].append('%s %s' % (time.ctime(), msg))
    self._Flush()

  def _CheckSerialNumber(self, serial):
    '''Checks if given serial number is in data store or not.

    Raises:
      ValueError if serial number is invalid.
    '''
    if serial in self.data_store:
      return True
    logging.error('Unknown serial number: %s', serial)
    raise ValueError('Unknown serial number: %s' % serial)

  def GetHWID(self, serial):
    '''See help(ShopFloorBase.GetHWID)'''
    logging.info('GetHWID(%s)', serial)
    self._CheckSerialNumber(serial)

    self._AppendStatus(serial, 'GetHWID')
    return self.data_store[serial]['hwid']

  def GetVPD(self, serial):
    '''See help(ShopFloorBase.GetVPD)'''
    logging.info('GetVPD(%s)', serial)
    self._CheckSerialNumber(serial)

    self._AppendStatus(serial, 'GetVPD')
    return self.data_store[serial]['vpd']

  def UploadReport(self, serial, report_blob):
    '''See help(ShopFloorBase.UploadReport)'''
    logging.info('UploadReport(%s, [%s])', serial, len(report_blob))
    self._CheckSerialNumber(serial)
    self.data_store[serial]['reports'].append(report_blob)
    self._AppendStatus(serial, 'UploadReport')

  def Finalize(self, serial):
    '''See help(ShopFloorBase.Finalize)'''
    logging.info('Finalize(%s)', serial)
    self._CheckSerialNumber(serial)
    self._AppendStatus(serial, 'Finalize')


def _CreateSampleDatabase():
  '''Returns sample database for shop floor system.'''
  # Format of sample database:
  # serial_number: { 'hwid': string,
  #                  'vpd': { 'ro': dict, 'rw': dict },
  #                  'reports': list,
  #                  'status': list }
  sample_hwids = ('TEST HWID A-A 4413',
                  'TEST HWID A-B 0951',
                  'TEST HWID2 A-A 3077',
                  'TEST HWID2 A-B 7631')
  # See gooftool/gft_vpd.py for mandatory fields.
  sample_vpds = ({'ro': {'keyboard_layout': 'xkb:us::eng',
                         'initial_locale': 'en-US',
                         'initial_timezone': 'America/Los_Angeles'},
                  'rw': {}},
                 {'ro': {'keyboard_layout': 'xkb:de::ger',
                         'initial_locale': 'de-DE',
                         # Note: Amsterdam is not a German city, but currently
                         # we use it for all UTC+1 regions. See test
                         # factory_SelectRegion for more information.
                         'initial_timezone': 'Europe/Amsterdam'},
                  'rw': {}})

  sample_database = {}
  # Valid serial numbers in sample: 0100 ~ 0199.
  sku_start = 100
  sku_count = 100
  sku_group_size = sku_count / len(sample_hwids)

  for i in xrange(sku_count):
    sku_index = i / sku_group_size
    data = {}
    serial_number = '%04d' % (sku_start + i)
    data['hwid'] = sample_hwids[sku_index]
    data['vpd'] = copy.deepcopy(sample_vpds[sku_index % len(sample_vpds)])
    # wifi_mac_addr is a sample VPD - not a mandatory field.
    data['vpd']['rw']['wifi_mac_addr'] = '0b:ad:f0:0d:01:%02x' % (sku_start + i)
    data['reports'] = []
    data['status'] = []
    sample_database[serial_number] = data
  return sample_database
