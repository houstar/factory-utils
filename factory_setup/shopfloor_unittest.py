#!/usr/bin/env python

# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for shop floor server."""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import xmlrpclib

import shopfloor
import shopfloor_server


class ShopFloorServerTest(unittest.TestCase):

  def setUp(self):
    '''Starts shop floor server and creates client proxy.'''
    self.server_port = shopfloor_server._DEFAULT_SERVER_PORT
    self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    self.data_dir = tempfile.mkdtemp(prefix='shopfloor_data.')
    self.registration_code_log = (
        os.path.join(self.data_dir, shopfloor.REGISTRATION_CODE_LOG_CSV))
    csv_source = os.path.join(self.base_dir, 'testdata', 'shopfloor',
                              'devices.csv')
    csv_work = os.path.join(self.data_dir, 'devices.csv')
    shutil.copyfile(csv_source, csv_work)
    os.mkdir(os.path.join(self.data_dir, shopfloor.UPDATE_DIR))
    os.mkdir(os.path.join(self.data_dir, shopfloor.UPDATE_DIR, 'factory'))

    cmd = ['python', os.path.join(self.base_dir, 'shopfloor_server.py'),
           '-q', '-a', 'localhost', '-p', str(self.server_port),
           '-m', 'shopfloor.simple.ShopFloor',
           '-d', self.data_dir]
    self.process = subprocess.Popen(cmd)
    self.proxy = xmlrpclib.ServerProxy('http://localhost:%s' % self.server_port,
                                       allow_none=True)
    # Waits the server to be ready, up to 1 second.
    for i in xrange(10):
      try:
        self.proxy.Ping()
        break
      except:
        time.sleep(0.1)
        continue
    else:
      self.fail('Server never came up')

  def tearDown(self):
    '''Terminates shop floor server'''
    self.process.terminate()
    self.process.wait()
    shutil.rmtree(self.data_dir)

  def testGetHWID(self):
    # Valid HWIDs range from CR001001 to CR001025
    for i in range(25):
      serial = 'CR0010%02d' % (i + 1)
      result = self.proxy.GetHWID(serial)
      self.assertTrue(result.startswith('MAGICA '))
      self.assertEqual(len(result.split(' ')), 4)

    # Test invalid serial numbers
    self.assertRaises(xmlrpclib.Fault, self.proxy.GetHWID, '0000')
    self.assertRaises(xmlrpclib.Fault, self.proxy.GetHWID, 'garbage')
    self.assertRaises(xmlrpclib.Fault, self.proxy.GetHWID, '')
    self.assertRaises(xmlrpclib.Fault, self.proxy.GetHWID, None)
    self.assertRaises(xmlrpclib.Fault, self.proxy.GetHWID, 'CR001000')
    self.assertRaises(xmlrpclib.Fault, self.proxy.GetHWID, 'CR001026')

  def testGetHWIDUpdater_None(self):
    self.assertEquals(None, self.proxy.GetHWIDUpdater())

  def testGetHWIDUpdater_One(self):
    with open(os.path.join(self.data_dir, 'hwid_updater.sh'), 'w') as f:
      f.write('foobar')
    self.assertEquals('foobar', self.proxy.GetHWIDUpdater().data)

  def testGetHWIDUpdater_Two(self):
    for i in (1, 2):
      open(os.path.join(self.data_dir, 'hwid_updater_%d.sh' % i), 'w').close()
    self.assertRaises(xmlrpclib.Fault, self.proxy.GetHWIDUpdater)

  def testGetVPD(self):
    # VPD fields defined in simple.csv
    RO_FIELDS = ('keyboard_layout', 'initial_locale', 'initial_timezone')
    RW_FIELDS_SET1 = ('wifi_mac', 'cellular_mac')
    RW_FIELDS_SET2 = ('wifi_mac', )

    vpd = self.proxy.GetVPD('CR001005')
    for field in RO_FIELDS:
      self.assertTrue(field in vpd['ro'] and vpd['ro'][field])
    for field in RW_FIELDS_SET1:
      self.assertTrue(field in vpd['rw'] and vpd['rw'][field])
    self.assertEqual(vpd['ro']['keyboard_layout'], 'xkb:us::eng')
    self.assertEqual(vpd['ro']['initial_locale'], 'en-US')
    self.assertEqual(vpd['ro']['initial_timezone'], 'America/Los_Angeles')
    self.assertEqual(vpd['rw']['wifi_mac'], '0b:ad:f0:0d:15:05')
    self.assertEqual(vpd['rw']['cellular_mac'], '70:75:65:6c:6c:65')

    vpd = self.proxy.GetVPD('CR001016')
    for field in RO_FIELDS:
      self.assertTrue(field in vpd['ro'] and vpd['ro'][field])
    for field in RW_FIELDS_SET2:
      self.assertTrue(field in vpd['rw'] and vpd['rw'][field])
    self.assertEqual(vpd['ro']['keyboard_layout'], 'xkb:us:intl:eng')
    self.assertEqual(vpd['ro']['initial_locale'], 'nl')
    self.assertEqual(vpd['ro']['initial_timezone'], 'Europe/Amsterdam')
    self.assertEqual(vpd['rw']['wifi_mac'], '0b:ad:f0:0d:15:10')
    self.assertEqual(vpd['rw']['cellular_mac'], '')

    # Checks MAC addresses
    for i in range(25):
      serial = 'CR0010%02d' % (i + 1)
      vpd = self.proxy.GetVPD(serial)
      wifi_mac = vpd['rw']['wifi_mac']
      self.assertEqual(wifi_mac, "0b:ad:f0:0d:15:%02x" % (i + 1))
      if i < 5:
        cellular_mac = vpd['rw']['cellular_mac']
        self.assertEqual(cellular_mac, "70:75:65:6c:6c:%02x" % (i + 0x61))

    # Checks invalid serial numbers
    self.assertRaises(xmlrpclib.Fault, self.proxy.GetVPD, 'MAGICA')
    return True

  def testUploadReport(self):
    # Upload simple blob
    blob = 'Simple Blob'
    report_name = 'simple_blob.rpt'
    report_path = os.path.join(self.data_dir, shopfloor.REPORTS_DIR,
                               report_name)
    self.proxy.UploadReport('CR001020', shopfloor.Binary('Simple Blob'),
                            report_name)
    self.assertTrue(os.path.exists(report_path))
    self.assertTrue(open(report_path).read(), blob)

    # Try to upload to invalid serial number
    self.assertRaises(xmlrpclib.Fault, self.proxy.UploadReport, 'CR00200', blob)

  def testFinalize(self):
    self.proxy.Finalize('CR001024')
    self.assertRaises(xmlrpclib.Fault, self.proxy.Finalize, '0999')

  def testGetTestMd5sum(self):
    md5_work = os.path.join(self.data_dir, shopfloor.UPDATE_DIR,
                            'factory', 'latest.md5sum')
    with open(md5_work, "w") as f:
      f.write('0891a16c456fcc322b656d5f91fbf060')
    self.assertEqual(self.proxy.GetTestMd5sum(),
                     '0891a16c456fcc322b656d5f91fbf060')
    os.remove(md5_work)

  def testGetTestMd5sumWithoutMd5sumFile(self):
    self.assertTrue(self.proxy.GetTestMd5sum() is None)

  def testGetRegistrationCodeMap(self):
    self.assertEquals(
        {'user': ('000000000000000000000000000000000000'
                  '0000000000000000000000000000190a55ad'),
         'group': ('010101010101010101010101010101010101'
                   '010101010101010101010101010162319fcc')},
        self.proxy.GetRegistrationCodeMap('CR001001'))

    # Make sure it was logged.
    log = open(self.registration_code_log).read()
    self.assertTrue(re.match(
        '^MAGICA MADOKA A-A 1214,'
        '000000000000000000000000000000000000'
        '0000000000000000000000000000190a55ad,'
        '010101010101010101010101010101010101'
        '010101010101010101010101010162319fcc,'
        '\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d\n', log), repr(log))

  def testUploadEvent(self):
    # Check if events dir is created.
    events_dir = os.path.join(self.data_dir, shopfloor.EVENTS_DIR)
    self.assertTrue(os.path.isdir(events_dir))

    # A new event file should be created.
    self.assertTrue(self.proxy.UploadEvent('LOG_C835C718',
                                           'PREAMBLE\n---\nEVENT_1\n'))
    event_file = os.path.join(events_dir, 'LOG_C835C718')
    self.assertTrue(os.path.isfile(event_file))

    # Additional events should be appended to existing event files.
    self.assertTrue(self.proxy.UploadEvent('LOG_C835C718',
                                           '---\nEVENT_2\n'))
    with open(event_file, 'r') as f:
      events = [event.strip() for event in f.read().split('---')]
      self.assertEqual(events[0], 'PREAMBLE')
      self.assertEqual(events[1], 'EVENT_1')
      self.assertEqual(events[2], 'EVENT_2')


if __name__ == '__main__':
  unittest.main()
