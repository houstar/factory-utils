# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


'''
(CHANGE THIS) This is a template for creating new implementation of factory shop
floor system module.
'''


# Add required python modules here.
import logging

# Always include 'shopfloor' for the abstract base class.
import shopfloor


class ShopFloorSystem(shopfloor.ShopFloorBase):
  '''(CHANGE THIS) Implementation for factory shop floor system.'''
  NAME = '(CHANGE THIS) Shopfloor system template'
  VERSION = 1

  def __init__(self, config=None):
    '''See help(ShopFloorBase.__init__)'''
    logging.info('Shop floor system started.')

  def GetHWID(self, serial):
    '''See help(ShopFloorBase.GetHWID)'''
    raise NotImplementedError('GetHWID')

  def GetVPD(self, serial):
    '''See help(ShopFloorBase.GetVPD)'''
    raise NotImplementedError('GetVPD')

  def UploadReport(self, serial, report_blob):
    '''See help(ShopFloorBase.UploadReport)'''
    raise NotImplementedError('UploadReport')

  def Finalize(self, serial):
    '''See help(ShopFloorBase.Finalize)'''
    raise NotImplementedError('Finalize')
