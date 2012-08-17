#!/usr/bin/env python
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


'''
This file starts a server for factory shop floor system.

To use it, invoke as a standalone program and assign the shop floor system
module you want to use (modules are located in "shopfloor" subdirectory).

Example:
  ./shopfloor_server -m shopfloor.simple.ShopFloor
'''


import hashlib
import imp
import logging
import optparse
import os
import shopfloor
import SimpleXMLRPCServer
from subprocess import Popen, PIPE


_DEFAULT_SERVER_PORT = 8082
# By default, this server is supposed to serve on same host running omaha
# server, accepting connections from client devices; so the address to bind is
# "all interfaces (0.0.0.0)". For partners running server on clients, they may
# want to change address to "localhost".
_DEFAULT_SERVER_ADDRESS = '0.0.0.0'


def _LoadShopFloorModule(name):
  '''Loads a specified python module.

  Args:
    name: Name of target module, in PACKAGE.MODULE.CLASS format.

  Returns:
    Module reference.
  '''
  (module_path, _, class_name) = name.rpartition('.')
  logging.debug('_LoadShopFloorModule: trying %s.%s', module_path, class_name)
  return getattr(__import__(module_path, fromlist=[class_name]), class_name)


def _RunAsServer(address, port, instance):
  '''Starts a XML-RPC server in given address and port.

  Args:
    address: Address to bind server.
    port: Port for server to listen.
    instance: Server instance for incoming XML RPC requests.

  Returns:
    Never returns if the server is started successfully, otherwise some
    exception will be raised.
  '''
  server = SimpleXMLRPCServer.SimpleXMLRPCServer((address, port),
                                                 allow_none=True,
                                                 logRequests=False)
  server.register_introspection_functions()
  server.register_instance(instance)
  logging.info('Server started: http://%s:%s "%s" version %s',
               address, port, instance.NAME, instance.VERSION)
  server.serve_forever()


def main():
  '''Main entry when being invoked by command line.'''
  parser = optparse.OptionParser()
  parser.add_option('-a', '--address', dest='address', metavar='ADDR',
                    default=_DEFAULT_SERVER_ADDRESS,
                    help='address to bind (default: %default)')
  parser.add_option('-p', '--port', dest='port', metavar='PORT', type='int',
                    default=_DEFAULT_SERVER_PORT,
                    help='port to bind (default: %default)')
  parser.add_option('-m', '--module', dest='module', metavar='MODULE',
                    default='shopfloor.ShopFloorBase',
                    help=('shop floor system module to load, in '
                          'PACKAGE.MODULE.CLASS format. E.g.: '
                          'shopfloor.simple.ShopFloor (default: %default)'))
  parser.add_option('-c', '--config', dest='config', metavar='CONFIG',
                    help='configuration data for shop floor system')
  parser.add_option('-d', '--data-dir', dest='data_dir', metavar='DIR',
                    default=os.path.join(
                        os.path.dirname(os.path.realpath(__file__)),
                        'shopfloor_data'),
                    help=('data directory for shop floor system '
                          '(default: %default)'))
  parser.add_option('-v', '--verbose', action='count', dest='verbose',
                    help='increase message verbosity')
  parser.add_option('-q', '--quiet', action='store_true', dest='quiet',
                    help='turn off verbose messages')
  (options, args) = parser.parse_args()
  if args:
    parser.error('Invalid args: %s' % ' '.join(args))

  if not options.module:
    parser.error('You need to assign the module to be loaded (-m).')

  verbosity_map = {0: logging.INFO,
                   1: logging.DEBUG}
  verbosity = verbosity_map.get(options.verbose or 0, logging.NOTSET)
  log_format = '%(asctime)s %(levelname)s '
  if options.verbose > 0:
    log_format += '(%(filename)s:%(lineno)d) '
  log_format += '%(message)s'
  logging.basicConfig(level=verbosity, format=log_format)
  if options.quiet:
    logging.disable(logging.INFO)

  try:
    logging.debug('Loading shop floor system module: %s', options.module)
    instance = _LoadShopFloorModule(options.module)()

    if not isinstance(instance, shopfloor.ShopFloorBase):
      logging.critical('Module does not inherit ShopFloorBase: %s',
                       options.module)
      exit(1)

    instance.data_dir = options.data_dir
    instance.config = options.config
    instance._InitBase()
    instance.Init()
  except:
    logging.exception('Failed loading module: %s', options.module)
    exit(1)

  # Find the HWID updater (if any).  Throw an exception if there are >1.
  hwid_updater_path = instance._GetHWIDUpdaterPath()
  if hwid_updater_path:
    logging.info('Using HWID updater %s (md5sum %s)' % (
        hwid_updater_path,
        hashlib.md5(open(hwid_updater_path).read()).hexdigest()))
  else:
    logging.warn('No HWID updater id currently available; add a single '
                 'file named %s to enable dynamic updating of HWIDs.' %
                 os.path.join(options.data_dir, shopfloor.HWID_UPDATER_PATTERN))

  try:
    instance._StartBase()
    logging.debug('Starting RPC server...')
    _RunAsServer(address=options.address, port=options.port, instance=instance)
  finally:
    instance._StopBase()


if __name__ == '__main__':
  main()
