#!/usr/bin/env python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


'''
This file starts a server for factory shop floor system.

To use it, invoke as a standalone program and assign the shop floor system
module you want to use (modules are located in "shopfloor" subdirectory).

Example:
  ./shopfloor_server -m shopfloor.sample.SampleShopFloor
'''


import imp
import logging
import optparse
import shopfloor
import SimpleXMLRPCServer


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
  logging.warn('Server started: http://%s:%s "%s" version %s',
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
                    help='(required) shop floor system module to load, in '
                    'PACKAGE.MODULE.CLASS format. Ex: shopfloor.sample.Sample')
  parser.add_option('-c', '--config', dest='config', metavar='CONFIG',
                    help='configuration data for shop floor system')
  parser.add_option('-v', '--verbose', action='count', dest='verbose',
                    help='increase message verbosity')
  parser.add_option('-q', '--quiet', action='store_true', dest='quiet',
                    help='turn off verbose messages')
  (options, args) = parser.parse_args()
  if args:
    parser.error('Invalid args: %s' % ' '.join(args))

  if not options.module:
    parser.error('You need to assign the module to be loaded (-m).')

  verbosity_map = {0: logging.WARNING,
                   1: logging.INFO,
                   2: logging.DEBUG}
  verbosity = verbosity_map.get(options.verbose or 0, logging.NOTSET)
  log_format = '%(asctime)s %(levelname)s '
  if options.verbose > 0:
    log_format += '(%(filename)s:%(lineno)d) '
  log_format += '%(message)s'
  logging.basicConfig(level=verbosity, format=log_format)
  if options.quiet:
    logging.disable(logging.CRITICAL)

  try:
    options.module = options.module
    logging.debug('Loading shop floor system module: %s', options.module)
    instance = _LoadShopFloorModule(options.module)(options.config)
    if not isinstance(instance, shopfloor.ShopFloorBase):
      logging.critical('Module does not inherit ShopFloorBase: %s',
                       options.module)
      exit(1)
  except:
    logging.exception('Failed loading module: %s', options.module)
    exit(1)

  logging.debug('Starting server...')
  _RunAsServer(address=options.address, port=options.port, instance=instance)


if __name__ == '__main__':
  main()
