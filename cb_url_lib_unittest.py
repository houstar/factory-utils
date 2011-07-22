#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for the cb_url_lib module."""

import formatter
import sys
import unittest

import cb_constants
import cb_url_lib

_LINK_NAME = 'href_atrribute/of_a_link'


class UrlListerTest(unittest.TestCase):
  """Unit tests for the UrlLister class."""

  def setUp(self):
    self.givenformatter = formatter.NullFormatter()

  def testReset(self):
    """Tests the reset method of class UrlLister."""
    with open('testdata/test_page_one_link.html', 'r') as page:
      parser = cb_url_lib.UrlLister(self.givenformatter)
      parser.urls = ['a_fake_link', 'another_fake_link']
      parser.reset()
      parser.feed(page.read())
      parser.close()
      self.assertEqual([_LINK_NAME], parser.urls)

  def testStart_aNoLinks(self):
    """Verify behavior when no links exist on given page."""
    with open('testdata/test_page_no_links.html', 'r') as page:
      parser = cb_url_lib.UrlLister(self.givenformatter)
      parser.feed(page.read())
      parser.close()
      self.assertEqual([], parser.urls)

  def testStart_aOneLink(self):
    """Verify parsing when one link present."""
    with open('testdata/test_page_one_link.html', 'r') as page:
      parser = cb_url_lib.UrlLister(self.givenformatter)
      parser.feed(page.read())
      parser.close()
      self.assertEqual([_LINK_NAME], parser.urls)

  def testStart_aManyLinks(self):
    """Verify parsing when many links present."""
    with open('testdata/test_page_many_links.html', 'r') as page:
      parser = cb_url_lib.UrlLister(self.givenformatter)
      parser.feed(page.read())
      parser.close()
      # sample page links taken from real chromeos-images index page
      expected = ['/stable-channel/x86-alex/',
                  'ChromeOS-0.12.433.269-r72d7eaa2-b198-x86-alex.zip',
                  'ChromeOS-factory-0.12.433.269-r72d7eaa2-b198-x86-alex.zip']
      actual = parser.urls
      self.assertEqual(expected, actual)


class TestDetermineUrl(unittest.TestCase):
  """Unit tests related to DetermineUrl."""

  def TestNoMatch(self):
    """Verify behvaior when no match exists."""
    pass

  def TestOneMatch(self):
    """Verify string returned upon a single good match."""
    pass

  def TestManyMatches(self):
    """verify string returned upon multiple good matches."""
    pass

#TODO(benwin) finish unit testing this module


if __name__ == "__main__":
  unittest.main()
