# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

'''Factory Update Server.

The factory update server is implemented as a thread to be started by shop floor
server.  It monitors the given state_dir and detects autotest.tar.bz2 file
changes and then sets up the new update files into update_dir (under state_dir).
It also starts an rsync server to serve update_dir for clients to fetch update
files.
'''

import logging
import os
import pyinotify
import shutil
import subprocess
import threading


UPDATE_DIR = 'autotest'
TARBALL_NAME = 'autotest.tar.bz2'
LATEST_SYMLINK = 'latest'
LATEST_MD5SUM = 'latest.md5sum'
DEFAULT_RSYNCD_PORT = 8083
RSYNCD_CONFIG_TEMPLATE = '''port = %(port)d
pid file = %(pidfile)s
log file = %(logfile)s
use chroot = no
[autotest]
  path = %(update_dir)s
  read only = yes
'''


def StartRsyncServer(port, state_dir, update_dir):
  configfile = os.path.join(state_dir, 'rsyncd.conf')
  pidfile = os.path.join(state_dir, 'rsyncd.pid')
  logfile = os.path.join(state_dir, 'rsyncd.log')
  data = RSYNCD_CONFIG_TEMPLATE % dict(port=port,
                                       pidfile=pidfile,
                                       logfile=logfile,
                                       update_dir=update_dir)
  with open(configfile, 'w') as f:
    f.write(data)

  p = subprocess.Popen(('rsync', '--daemon', '--no-detach',
                        '--config=%s' % configfile))
  logging.debug('Rsync server (pid %d) started on port %d', p.pid, port)
  return p


def StopRsyncServer(rsyncd_process):
  logging.debug('Stopping rsync server (pid %d)', rsyncd_process.pid)
  rsyncd_process.terminate()
  rsyncd_process.wait()
  logging.debug('Rsync server stopped')


def CalculateMd5sum(filename):
  p = subprocess.Popen(('md5sum', filename), stdout=subprocess.PIPE)
  output, _ = p.communicate()
  return output.split()[0]


class HandleEvents(pyinotify.ProcessEvent):

  def __init__(self, update_dir):
    self.update_dir = update_dir

  def process_IN_CLOSE_WRITE(self, event):
    if event.name == TARBALL_NAME:
      # Calculate MD5.
      md5sum = CalculateMd5sum(event.pathname)
      logging.info('Found new ' + TARBALL_NAME + ' (%s)', md5sum)

      # Create subfolder to hold tarball contents.
      subfolder = os.path.join(self.update_dir, md5sum)
      if os.path.exists(subfolder):
        logging.error('Subfolder %s already exists', subfolder)
        return
      try:
        os.mkdir(subfolder)
      except Exception:
        logging.error('Unable to create subfolder %s', subfolder)
        return

      # Extract tarball.
      try:
        subprocess.check_call(('tar', '-xjf', event.pathname, '-C', subfolder))
      except subprocess.CalledProcessError:
        logging.error('Failed to extract update files to subfolder %s',
                      subfolder)
        shutil.rmtree(subfolder)  # Clean up on error.
        return

      # Update symlink and latest.md5sum.
      linkname = os.path.join(self.update_dir, LATEST_SYMLINK)
      if os.path.islink(linkname):
        os.remove(linkname)
      os.symlink(md5sum, linkname)
      with open(os.path.join(self.update_dir, LATEST_MD5SUM), 'w') as f:
        f.write(md5sum)
      logging.info('New update files (%s) setup complete', md5sum)


class FactoryUpdateServer(threading.Thread):

  def __init__(self, state_dir, rsyncd_port=DEFAULT_RSYNCD_PORT):
    threading.Thread.__init__(self)
    self.state_dir = state_dir
    self.update_dir = os.path.join(state_dir, UPDATE_DIR)
    if not os.path.exists(self.update_dir):
      os.mkdir(self.update_dir)
    self._stop_event = threading.Event()
    self._rsyncd = StartRsyncServer(rsyncd_port, state_dir, self.update_dir)

  def run(self):
    wm = pyinotify.WatchManager()
    notifier = pyinotify.Notifier(wm, HandleEvents(self.update_dir))
    mask = pyinotify.IN_CLOSE_WRITE
    wm.add_watch(self.state_dir, mask)
    try:
      while True:
        notifier.process_events()
        if self._stop_event.is_set():
          break
        if notifier.check_events(500):
          notifier.read_events()
    finally:
      notifier.stop()
    logging.debug('Factory update server stopped')

  def stop(self):
    StopRsyncServer(self._rsyncd)
    self._stop_event.set()
    self.join()
