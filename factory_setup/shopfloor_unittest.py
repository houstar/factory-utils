#!/usr/bin/env python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for shop floor server."""

import os
import shopfloor_server
import subprocess
import sys
import tempfile
import time
import unittest
import xmlrpclib


class ShopFloorServerTest(unittest.TestCase):

  def setUp(self):
    '''Starts shop floor server and creates client proxy.'''
    self.server_port = shopfloor_server._DEFAULT_SERVER_PORT
    self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    (handle, self.config_file) = tempfile.mkstemp(prefix='sft')
    os.close(handle)
    cmd = ['python', os.path.join(self.base_dir, 'shopfloor_server.py'),
           '-q', '-a', 'localhost', '-p', str(self.server_port),
           '-c', self.config_file, '-m', 'shopfloor.sample.SampleShopFloor']
    self.process = subprocess.Popen(cmd)
    self.proxy = xmlrpclib.ServerProxy('http://localhost:%s' % self.server_port,
                                       allow_none=True)
    # Waits the server to be ready, up to 1 second.
    for i in xrange(10):
      try:
        self.proxy.system.listMethods()
      except:
        time.sleep(0.1)
        continue

  def tearDown(self):
    '''Terminates shop floor server'''
    self.process.terminate()
    os.remove(self.config_file)

  def testGetHWID(self):
    sample_hwids = ('TEST HWID A-A 4413',
                    'TEST HWID A-B 0951',
                    'TEST HWID2 A-A 3077',
                    'TEST HWID2 A-B 7631')
    # Simulating 100 devices, starting at "0100" and grouped according to number
    # of sample_hwids
    sku_start = 100
    sku_count = 100
    sku_group = sku_count / len(sample_hwids)
    for i in xrange(sku_count):
      serial = '%04d' % (sku_start + i)
      hwid = sample_hwids[i / sku_group]
      result = self.proxy.GetHWID(serial)
      self.assertEqual(result, hwid)

    # Test invalid serial numbers
    self.assertRaises(xmlrpclib.Fault, self.proxy.GetHWID, '0000')
    self.assertRaises(xmlrpclib.Fault, self.proxy.GetHWID, 'garbage')
    self.assertRaises(xmlrpclib.Fault, self.proxy.GetHWID, '')

  def testGetVPD(self):
    vpd = self.proxy.GetVPD('0100')
    self.assertTrue('ro' in vpd)
    self.assertTrue('rw' in vpd)
    self.assertTrue(type(vpd['ro']) is dict)
    self.assertTrue(type(vpd['rw']) is dict)
    mandatory_fields = ('keyboard_layout',
                        'initial_locale',
                        'initial_timezone')
    for field in mandatory_fields:
      self.assertTrue(field in vpd['ro'])
    self.assertEqual(vpd['rw']['wifi_mac_addr'], '0b:ad:f0:0d:01:64')

    vpd = self.proxy.GetVPD('0199')
    self.assertEqual(vpd['rw']['wifi_mac_addr'], '0b:ad:f0:0d:01:c7')

  def testUploadReport(self):
    blob = 'report data'
    self.proxy.UploadReport('0101', blob)
    self.assertRaises(xmlrpclib.Fault, self.proxy.UploadReport, '1000', blob)

  def testFinalize(self):
    self.proxy.Finalize('0102')
    self.assertRaises(xmlrpclib.Fault, self.proxy.Finalize, '0999')

if __name__ == '__main__':
  unittest.main()
