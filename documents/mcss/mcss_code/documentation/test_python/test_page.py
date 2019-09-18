#
#   This file is part of m.css.
#
#   Copyright © 2017, 2018, 2019 Vladimír Vondruš <mosra@centrum.cz>
#
#   Permission is hereby granted, free of charge, to any person obtaining a
#   copy of this software and associated documentation files (the "Software"),
#   to deal in the Software without restriction, including without limitation
#   the rights to use, copy, modify, merge, publish, distribute, sublicense,
#   and/or sell copies of the Software, and to permit persons to whom the
#   Software is furnished to do so, subject to the following conditions:
#
#   The above copyright notice and this permission notice shall be included
#   in all copies or substantial portions of the Software.
#
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
#   THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#   FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#   DEALINGS IN THE SOFTWARE.
#

import matplotlib
import os
import re
import subprocess

from distutils.version import LooseVersion

from . import BaseTestCase

def dot_version():
    return re.match(".*version (?P<version>\d+\.\d+\.\d+).*", subprocess.check_output(['dot', '-V'], stderr=subprocess.STDOUT).decode('utf-8').strip()).group('version')

class Page(BaseTestCase):
    def test(self):
        self.run_python({
            'INPUT_PAGES': ['index.rst', 'another.rst']
        })
        self.assertEqual(*self.actual_expected_contents('index.html'))
        self.assertEqual(*self.actual_expected_contents('another.html'))
        self.assertEqual(*self.actual_expected_contents('pages.html'))

class InputSubdir(BaseTestCase):
    def test(self):
        self.run_python({
            'INPUT': 'sub',
            'INPUT_PAGES': ['index.rst']
        })
        # The same output as Page, just the file is taken from elsewhere
        self.assertEqual(*self.actual_expected_contents('index.html', '../page/index.html'))

class Plugins(BaseTestCase):
    def test(self):
        self.run_python({
            # Test all of them to check the registration works well
            'PLUGINS': [
                'm.abbr',
                'm.code',
                'm.components',
                'm.dot',
                'm.dox',
                'm.gh',
                'm.gl',
                'm.images',
                'm.link',
                'm.plots',
                'm.vk',
                'fancyline'
            ],
            'PLUGIN_PATHS': ['plugins'],
            'INPUT_PAGES': ['index.rst', 'dot.rst', 'plots.rst'],
            'M_HTMLSANITY_SMART_QUOTES': True,
            'M_DOT_FONT': 'DejaVu Sans',
            'M_PLOTS_FONT': 'DejaVu Sans',
            'M_DOX_TAGFILES': [
                (os.path.join(self.path, '../../../doc/documentation/corrade.tag'), 'https://doc.magnum.graphics/corrade/')
            ]
        })
        self.assertEqual(*self.actual_expected_contents('index.html'))
        # The output is different for older Graphviz
        self.assertEqual(*self.actual_expected_contents('dot.html', 'dot.html' if LooseVersion(dot_version()) >= LooseVersion("2.40.1") else 'dot-238.html'))
        # I assume this will be a MASSIVE ANNOYANCE at some point as well so
        # keeping it separate
        self.assertEqual(*self.actual_expected_contents('plots.html'))
        self.assertTrue(os.path.exists(os.path.join(self.path, 'output/tiny.png')))

        import fancyline
        self.assertEqual(fancyline.pre_page_call_count, 4)
        self.assertEqual(fancyline.post_run_call_count, 1)
