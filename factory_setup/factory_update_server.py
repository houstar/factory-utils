# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

'''Factory Update Server.

The factory update server is implemented as a thread to be started by
shop floor server.  It monitors the given state_dir and detects
autotest.tar.bz2 file changes and then sets up the new update files
into autotest_dir (under state_dir).  It also starts an rsync server
to serve autotest_dir for clients to fetch update files.
'''

import errno
import logging
import os
import shutil
import subprocess
import threading
import time


AUTOTEST_DIR = 'autotest'
TARBALL_NAME = 'autotest.tar.bz2'
LATEST_SYMLINK = 'latest'
LATEST_MD5SUM = 'latest.md5sum'
MD5SUM = 'MD5SUM'
DEFAULT_RSYNCD_PORT = 8083
RSYNCD_CONFIG_TEMPLATE = '''port = %(port)d
pid file = %(pidfile)s
log file = %(logfile)s
use chroot = no
[autotest]
  path = %(autotest_dir)s
  read only = yes
'''


def StartRsyncServer(port, state_dir, autotest_dir):
  configfile = os.path.join(state_dir, 'rsyncd.conf')
  pidfile = os.path.join(state_dir, 'rsyncd.pid')
  if os.path.exists(pidfile):
    # Since rsyncd will not overwrite it if it already exists
    os.unlink(pidfile)
  logfile = os.path.join(state_dir, 'rsyncd.log')
  data = RSYNCD_CONFIG_TEMPLATE % dict(port=port,
                                       pidfile=pidfile,
                                       logfile=logfile,
                                       autotest_dir=autotest_dir)
  with open(configfile, 'w') as f:
    f.write(data)

  p = subprocess.Popen(('rsync', '--daemon', '--no-detach',
                        '--config=%s' % configfile))
  logging.info('Rsync server (pid %d) started on port %d', p.pid, port)
  return p


def StopRsyncServer(rsyncd_process):
  logging.info('Stopping rsync server (pid %d)', rsyncd_process.pid)
  rsyncd_process.terminate()

  # If not terminated in a second, send a kill -9.
  def WaitAndKill():
    time.sleep(1)
    try:
      rsyncd_process.kill()
    except:
      pass
  thread = threading.Thread(target=WaitAndKill)
  thread.daemon = True
  thread.start()

  rsyncd_process.wait()
  logging.debug('Rsync server stopped')


def CalculateMd5sum(filename):
  p = subprocess.Popen(('md5sum', filename), stdout=subprocess.PIPE)
  output, _ = p.communicate()
  return output.split()[0]


class FactoryUpdateServer():

  def __init__(self, state_dir, rsyncd_port=DEFAULT_RSYNCD_PORT,
               poll_interval_sec=1):
    self.state_dir = state_dir
    self.autotest_dir = os.path.join(state_dir, AUTOTEST_DIR)
    self.rsyncd_port = rsyncd_port
    if not os.path.exists(self.autotest_dir):
      os.mkdir(self.autotest_dir)
    self.poll_interval_sec = poll_interval_sec
    self._stop_event = threading.Event()
    self._rsyncd = StartRsyncServer(rsyncd_port, state_dir, self.autotest_dir)
    self._tarball_path = os.path.join(self.state_dir, TARBALL_NAME)

    self._thread = None
    self._last_stat = None
    self._run_count = 0
    self._update_count = 0
    self._errors = 0

  def Start(self):
    assert not self._thread
    self._thread = threading.Thread(target=self.Run)
    self._thread.start()

  def Stop(self):
    if self._rsyncd:
      StopRsyncServer(self._rsyncd)
      self._rsyncd = None

    self._stop_event.set()

    if self._thread:
      self._thread.join()
      self._thread = None

  def _HandleTarball(self):
    new_tarball_path = self._tarball_path + '.new'

    # Copy the tarball to avoid possible race condition.
    shutil.copyfile(self._tarball_path, new_tarball_path)

    # Calculate MD5.
    md5sum = CalculateMd5sum(new_tarball_path)
    logging.info('Processing tarball ' + self._tarball_path + ' (md5sum=%s)',
                 md5sum)

    # Move to a file containing the MD5.
    final_tarball_path = self._tarball_path + '.' + md5sum
    os.rename(new_tarball_path, final_tarball_path)

    # Create subfolder to hold tarball contents.
    final_subfolder = os.path.join(self.autotest_dir, md5sum)
    final_md5sum = os.path.join(final_subfolder, AUTOTEST_DIR, MD5SUM)
    if os.path.exists(final_subfolder):
      if not (os.path.exists(final_md5sum) and
              open(final_md5sum).read().strip() == md5sum):
        logging.warn('Update directory %s appears not to be set up properly '
                     '(missing or bad MD5SUM); delete it and restart update '
                     'server?', final_subfolder)
        return
      logging.info('Update is already deployed into %s', final_subfolder)
    else:
      new_subfolder = final_subfolder + '.new'
      if os.path.exists(new_subfolder):
        shutil.rmtree(new_subfolder)
      os.mkdir(new_subfolder)

      # Extract tarball.
      success = False
      try:
        try:
          logging.info('Staged into %s', new_subfolder)
          subprocess.check_call(('tar', '-xjf', final_tarball_path,
                                 '-C', new_subfolder))
        except subprocess.CalledProcessError:
          logging.error('Failed to extract update files to subfolder %s',
                        new_subfolder)
          return

        autotest_dir = os.path.join(new_subfolder, AUTOTEST_DIR)
        if not os.path.exists(autotest_dir):
          logging.error('Tarball does not contain autotest directory')
          return

        with open(os.path.join(autotest_dir, MD5SUM), 'w') as f:
          f.write(md5sum)

        # Extracted and verified.  Move it in place.
        os.rename(new_subfolder, final_subfolder)
        logging.info('Moved to final directory %s', final_subfolder)

        success = True
        self._update_count += 1
      finally:
        if os.path.exists(new_subfolder):
          shutil.rmtree(new_subfolder, ignore_errors=True)
        if (not success) and os.path.exists(final_subfolder):
          shutil.rmtree(final_subfolder, ignore_errors=True)

    # Update symlink and latest.md5sum.
    linkname = os.path.join(self.autotest_dir, LATEST_SYMLINK)
    if os.path.islink(linkname):
      os.remove(linkname)
    os.symlink(md5sum, linkname)
    with open(os.path.join(self.autotest_dir, LATEST_MD5SUM), 'w') as f:
      f.write(md5sum)
    logging.info('Update files (%s) setup complete', md5sum)

  def Run(self):
    while True:
      try:
        self.RunOnce()
      except:
        logging.exception('Error in event loop')

      self._stop_event.wait(self.poll_interval_sec)
      if self._stop_event.is_set():
        break

  def RunOnce(self):
    try:
      self._run_count += 1

      try:
        stat = os.stat(self._tarball_path)
      except OSError as e:
        if e.errno == errno.ENOENT:
          # File doesn't exist
          return
        raise

      if (self._last_stat and
          ((stat.st_mtime, stat.st_size) ==
           (self._last_stat.st_mtime, self._last_stat.st_size))):
        # No change
        return

      self._last_stat = stat
      try:
        with open(os.devnull, "w") as devnull:
          logging.info('Verifying integrity of tarball %s', self._tarball_path)
          subprocess.check_call(['tar', '-tjf', self._tarball_path],
                                stdout=devnull, stderr=devnull)
      except subprocess.CalledProcessError:
        # E.g., still copying
        logging.warn('Tarball %s (%d bytes) is corrupt or incomplete',
                     self._tarball_path, stat.st_size)
        return

      # Re-stat in case it finished being written while we were
      # verifying it.
      self._last_stat = os.stat(self._tarball_path)
      self._HandleTarball()
    except:
      self._errors += 1
      raise
