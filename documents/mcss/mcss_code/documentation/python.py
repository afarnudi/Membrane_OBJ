#!/usr/bin/env python3

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

import argparse
import copy
import docutils
import enum
import urllib.parse
import hashlib
import html
import importlib
import inspect
import logging
import mimetypes
import os
import re
import sys
import shutil
import typing

from enum import Enum
from types import SimpleNamespace as Empty
from importlib.machinery import SourceFileLoader
from typing import Tuple, Dict, Set, Any, List, Callable, Optional
from urllib.parse import urljoin
from distutils.version import LooseVersion
from docutils.transforms import Transform

import jinja2

from _search import CssClass, ResultFlag, ResultMap, Trie, serialize_search_data, base85encode_search_data, searchdata_format_version, searchdata_filename, searchdata_filename_b85

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '../plugins'))
import m.htmlsanity

default_templates = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates/python/')

special_pages = ['index', 'modules', 'classes', 'pages']

class EntryType(Enum):
    # Order must match the search_type_map below; first value is reserved for
    # ResultFlag.ALIAS
    PAGE = 1
    MODULE = 2
    CLASS = 3
    FUNCTION = 4
    PROPERTY = 5
    ENUM = 6
    ENUM_VALUE = 7
    DATA = 8

    # Types not exposed to search are below

    # One of files from special_pages. Doesn't make sense to include in the
    # search.
    SPECIAL = 9
    # Denotes a potentially overloaded pybind11 function. Has to be here to
    # be able to distinguish between zero-argument normal and pybind11
    # functions. To search it's exposed as FUNCTION.
    OVERLOADED_FUNCTION = 10

# Order must match the EntryType above
search_type_map = [
    (CssClass.SUCCESS, "page"),
    (CssClass.PRIMARY, "module"),
    (CssClass.PRIMARY, "class"),
    (CssClass.INFO, "func"),
    (CssClass.WARNING, "property"),
    (CssClass.PRIMARY, "enum"),
    (CssClass.DEFAULT, "enum val"),
    (CssClass.DEFAULT, "data")
]

def default_url_formatter(type: EntryType, path: List[str]) -> Tuple[str, str]:
    # TODO: what about nested pages, how to format?
    url = '.'.join(path) + '.html'
    assert '/' not in url # TODO
    return url, url

def default_id_formatter(type: EntryType, path: List[str]) -> str:
    # Encode pybind11 function overloads into the anchor (hash them, like Rust
    # does)
    if type == EntryType.OVERLOADED_FUNCTION:
        return path[0] + '-' + hashlib.sha1(', '.join([str(i) for i in path[1:]]).encode('utf-8')).hexdigest()[:5]

    if type == EntryType.ENUM_VALUE:
        assert len(path) == 2
        return '-'.join(path)

    assert len(path) == 1
    return path[0]

default_config = {
    'PROJECT_TITLE': 'My Python Project',
    'PROJECT_SUBTITLE': None,
    'MAIN_PROJECT_URL': None,
    'INPUT': None,
    'OUTPUT': 'output',
    'INPUT_MODULES': [],
    'INPUT_PAGES': [],
    'INPUT_DOCS': [],
    'OUTPUT': 'output',
    'THEME_COLOR': '#22272e',
    'FAVICON': 'favicon-dark.png',
    'STYLESHEETS': [
        'https://fonts.googleapis.com/css?family=Source+Sans+Pro:400,400i,600,600i%7CSource+Code+Pro:400,400i,600',
        '../css/m-dark+documentation.compiled.css'],
    'EXTRA_FILES': [],
    'LINKS_NAVBAR1': [
        ('Pages', 'pages', []),
        ('Modules', 'modules', []),
        ('Classes', 'classes', [])],
    'LINKS_NAVBAR2': [],

    'PAGE_HEADER': None,
    'FINE_PRINT': '[default]',
    'FORMATTED_METADATA': ['summary'],

    'PLUGINS': [],
    'PLUGIN_PATHS': [],

    'CLASS_INDEX_EXPAND_LEVELS': 1,
    'CLASS_INDEX_EXPAND_INNER': False,

    'PYBIND11_COMPATIBILITY': False,

    'SEARCH_DISABLED': False,
    'SEARCH_DOWNLOAD_BINARY': False,
    'SEARCH_HELP': """.. raw:: html

    <p class="m-noindent">Search for modules, classes, functions and other
    symbols. You can omit any prefix from the symbol path; adding a <code>.</code>
    suffix lists all members of given symbol.</p>
    <p class="m-noindent">Use <span class="m-label m-dim">&darr;</span>
    / <span class="m-label m-dim">&uarr;</span> to navigate through the list,
    <span class="m-label m-dim">Enter</span> to go.
    <span class="m-label m-dim">Tab</span> autocompletes common prefix, you can
    copy a link to the result using <span class="m-label m-dim">⌘</span>
    <span class="m-label m-dim">L</span> while <span class="m-label m-dim">⌘</span>
    <span class="m-label m-dim">M</span> produces a Markdown link.</p>
""",
    'SEARCH_BASE_URL': None,
    'SEARCH_EXTERNAL_URL': None,

    'URL_FORMATTER': default_url_formatter,
    'ID_FORMATTER': default_id_formatter
}

class State:
    def __init__(self, config):
        self.config = config
        self.module_mapping: Dict[str, str] = {}
        self.module_docs: Dict[str, Dict[str, str]] = {}
        self.class_docs: Dict[str, Dict[str, str]] = {}
        self.enum_docs: Dict[str, Dict[str, str]] = {}
        self.function_docs: Dict[str, Dict[str, str]] = {}
        self.property_docs: Dict[str, Dict[str, str]] = {}
        self.data_docs: Dict[str, Dict[str, str]] = {}
        self.external_data: Set[str] = set()

        self.hooks_pre_page: List = []
        self.hooks_post_run: List = []

        self.name_map: Dict[str, Empty] = {}
        self.search: List[Any] = []

        self.crawled: Set[object] = set()

def map_name_prefix(state: State, type: str) -> str:
    for prefix, replace in state.module_mapping.items():
        if type == prefix or type.startswith(prefix + '.'):
            return replace + type[len(prefix):]

    # No mapping found, return the type as-is
    return type

def object_type(state: State, object) -> EntryType:
    if inspect.ismodule(object): return EntryType.MODULE
    if inspect.isclass(object):
        if (inspect.isclass(object) and issubclass(object, enum.Enum)) or (state.config['PYBIND11_COMPATIBILITY'] and hasattr(object, '__members__')):
            return EntryType.ENUM
        else: return EntryType.CLASS
    if inspect.isfunction(object) or inspect.isbuiltin(object) or inspect.isroutine(object):
        return EntryType.FUNCTION
    if inspect.isdatadescriptor(object):
        return EntryType.PROPERTY
    # Assume everything else is data. The builtin help help() (from pydoc) does
    # the same: https://github.com/python/cpython/blob/d29b3dd9227cfc4a23f77e99d62e20e063272de1/Lib/pydoc.py#L113
    if not inspect.isframe(object) and not inspect.istraceback(object) and not inspect.iscode(object):
        return EntryType.DATA

    # caller should print a warning in this case
    return None # pragma: no cover

# Builtin dunder functions have hardcoded docstrings. This is totally useless
# to have in the docs, so filter them out. Uh... kinda ugly.
_filtered_builtin_functions = set([
    ('__delattr__', "Implement delattr(self, name)."),
    ('__eq__', "Return self==value."),
    ('__ge__', "Return self>=value."),
    ('__getattribute__', "Return getattr(self, name)."),
    ('__gt__', "Return self>value."),
    ('__hash__', "Return hash(self)."),
    ('__init__', "Initialize self.  See help(type(self)) for accurate signature."),
    ('__init_subclass__',
        "This method is called when a class is subclassed.\n\n"
        "The default implementation does nothing. It may be\n"
        "overridden to extend subclasses.\n"),
    ('__le__', "Return self<=value."),
    ('__lt__', "Return self<value."),
    ('__ne__', "Return self!=value."),
    ('__new__',
        "Create and return a new object.  See help(type) for accurate signature."),
    ('__repr__', "Return repr(self)."),
    ('__setattr__', "Implement setattr(self, name, value)."),
    ('__str__', "Return str(self)."),
    ('__subclasshook__',
        "Abstract classes can override this to customize issubclass().\n\n"
        "This is invoked early on by abc.ABCMeta.__subclasscheck__().\n"
        "It should return True, False or NotImplemented.  If it returns\n"
        "NotImplemented, the normal algorithm is used.  Otherwise, it\n"
        "overrides the normal algorithm (and the outcome is cached).\n")
])

# Python 3.6 has slightly different docstrings than 3.7
if LooseVersion(sys.version) >= LooseVersion("3.7"):
    _filtered_builtin_functions.update({
        ('__dir__', "Default dir() implementation."),
        ('__format__', "Default object formatter."),
        ('__reduce__', "Helper for pickle."),
        ('__reduce_ex__', "Helper for pickle."),
        ('__sizeof__', "Size of object in memory, in bytes."),
    })
else:
    _filtered_builtin_functions.update({
        ('__dir__', "__dir__() -> list\ndefault dir() implementation"),
        ('__format__', "default object formatter"),
        ('__reduce__', "helper for pickle"),
        ('__reduce_ex__', "helper for pickle"),
        ('__sizeof__', "__sizeof__() -> int\nsize of object in memory, in bytes")
    })

_filtered_builtin_properties = set([
    ('__weakref__', "list of weak references to the object (if defined)")
])

def crawl_enum(state: State, path: List[str], enum_):
    enum_entry = Empty()
    enum_entry.type = EntryType.ENUM
    enum_entry.object = enum_
    enum_entry.path = path
    enum_entry.values = []

    if issubclass(enum_, enum.Enum):
        for i in enum_:
            subpath = path + [i.name]
            entry = Empty()
            entry.type = EntryType.ENUM_VALUE
            entry.path = subpath
            state.name_map['.'.join(subpath)] = entry

    elif state.config['PYBIND11_COMPATIBILITY']:
        assert hasattr(enum_, '__members__')

        for name in enum_.__members__:
            subpath = path + [name]
            entry = Empty()
            entry.type = EntryType.ENUM_VALUE
            entry.path = subpath
            state.name_map['.'.join(subpath)] = entry

    # Add itself to the name map
    state.name_map['.'.join(path)] = enum_entry

def crawl_class(state: State, path: List[str], class_):
    assert inspect.isclass(class_)

    # TODO: if this fires, it means there's a class duplicated in more than one
    # __all__ (or it gets picked up implicitly and then in __all__) -- how to
    # handle gracefully?
    assert id(class_) not in state.crawled
    state.crawled.add(id(class_))

    class_entry = Empty()
    class_entry.type = EntryType.CLASS
    class_entry.object = class_
    class_entry.path = path
    class_entry.url = state.config['URL_FORMATTER'](EntryType.CLASS, path)[1]
    class_entry.members = []

    for name, object in inspect.getmembers(class_):
        type = object_type(state, object)
        subpath = path + [name]

        # Crawl the subclasses recursively (they also add itself to the
        # name_map)
        if type == EntryType.CLASS:
            if name in ['__base__', '__class__']: continue # TODO
            if name.startswith('_'): continue

            crawl_class(state, subpath, object)

        # Crawl enum values (they also add itself ot the name_map)
        elif type == EntryType.ENUM:
            if name.startswith('_'): continue

            crawl_enum(state, subpath, object)

        # Add other members directly
        else:
            # Filter out private / unwanted members
            if type == EntryType.FUNCTION:
                # Filter out underscored methods (but not dunder methods such
                # as __init__)
                if name.startswith('_') and not (name.startswith('__') and name.endswith('__')): continue
                # Filter out dunder methods that don't have their own docs
                if name.startswith('__') and (name, object.__doc__) in _filtered_builtin_functions: continue
            elif type == EntryType.PROPERTY:
                if (name, object.__doc__) in _filtered_builtin_properties: continue
                if name.startswith('_'): continue # TODO: are there any dunder props?
            elif type == EntryType.DATA:
                if name.startswith('_'): continue
            else: # pragma: no cover
                assert type is None; continue # ignore unknown object types

            entry = Empty()
            entry.type = type
            entry.object = object
            entry.path = subpath
            state.name_map['.'.join(subpath)] = entry

        class_entry.members += [name]

    # Add itself to the name map
    state.name_map['.'.join(path)] = class_entry

def crawl_module(state: State, path: List[str], module) -> List[Tuple[List[str], object]]:
    assert inspect.ismodule(module)

    # Assume this module is not crawled yet -- the parent crawl shouldn't even
    # put it to members if it's crawled already. Otherwise add itself to
    # the list of crawled objects to avoid going through it again.
    assert id(module) not in state.crawled
    state.crawled.add(id(module))

    # This module isn't a duplicate, thus we can now safely add itself to
    # parent's members (if there's a parent)
    if len(path) > 1: state.name_map['.'.join(path[:-1])].members += [path[-1]]

    module_entry = Empty()
    module_entry.type = EntryType.MODULE
    module_entry.object = module
    module_entry.path = path
    module_entry.url = state.config['URL_FORMATTER'](EntryType.MODULE, path)[1]
    module_entry.members = []

    # This gets returned to ensure the modules get processed in a breadth-first
    # order
    submodules_to_crawl: List[Tuple[List[str], object]] = []

    # This is actually complicated -- if the module defines __all__, use that.
    # The __all__ is meant to expose the public API, so we don't filter out
    # underscored things.
    if hasattr(module, '__all__'):
        # Names exposed in __all__ could be also imported from elsewhere, for
        # example this is a common pattern with native libraries and we want
        # Foo, Bar, submodule and *everything* in submodule to be referred to
        # as `library.RealName` (`library.submodule.func()`, etc.) instead of
        # `library._native.Foo`, `library._native.sub.func()` etc.
        #
        #   from ._native import Foo as PublicName
        #   from ._native import sub as submodule
        #   __all__ = ['PublicName', 'submodule']
        #
        # The name references can be cyclic so extract the mapping in a
        # separate pass before everything else.
        for name in module.__all__:
            # Everything available in __all__ is already imported, so get those
            # directly
            object = getattr(module, name)
            subpath = path + [name]

            # Modules have __name__ while other objects have __module__, need
            # to check both.
            if inspect.ismodule(object) and object.__name__ != '.'.join(subpath):
                assert object.__name__ not in state.module_mapping
                state.module_mapping[object.__name__] = '.'.join(subpath)
            elif hasattr(object, '__module__'):
                subname = object.__module__ + '.' + object.__name__
                if subname != '.'.join(subpath):
                    assert subname not in state.module_mapping
                    state.module_mapping[subname] = '.'.join(subpath)

        # Now extract the actual docs
        for name in module.__all__:
            object = getattr(module, name)
            subpath = path + [name]
            type = object_type(state, object)

            # Crawl the submodules and subclasses recursively (they also add
            # itself to the name_map), add other members directly.
            if not type: # pragma: no cover
                logging.warning("unknown symbol %s in %s", name, '.'.join(path))
                continue
            elif type == EntryType.MODULE:
                # TODO: this might fire if a module is in __all__ after it was
                # picked up implicitly before -- how to handle gracefully?
                assert id(object) not in state.crawled
                submodules_to_crawl += [(subpath, object)]
                # Not adding to module_entry.members, done by the nested
                # crawl_module() itself if it is sure that it isn't a
                # duplicated module
                continue
            elif type == EntryType.CLASS:
                crawl_class(state, subpath, object)
            elif type == EntryType.ENUM:
                crawl_enum(state, subpath, object)
            else:
                assert type in [EntryType.FUNCTION, EntryType.DATA]
                entry = Empty()
                entry.type = type
                entry.object = object
                entry.path = subpath
                state.name_map['.'.join(subpath)] = entry

            module_entry.members += [name]

    # Otherwise, enumerate the members using inspect. However, inspect lists
    # also imported modules, functions and classes, so take only those which
    # have __module__ equivalent to `path`.
    else:
        for name, object in inspect.getmembers(module):
            # Filter out underscored names
            if name.startswith('_'): continue

            # If this is not a module, check if the enclosing module of the
            # object is what expected. If not, it's a class/function/...
            # imported from elsewhere and we don't want those.
            # TODO: xml.dom.domreg says the things from it should be imported
            #   as xml.dom.foo() and this check discards them, can it be done
            #   without manually adding __all__?
            if not inspect.ismodule(object):
                # Variables don't have the __module__ attribute, so check for
                # its presence. Right now *any* variable will be present in the
                # output, as there is no way to check where it comes from.
                if hasattr(object, '__module__') and map_name_prefix(state, object.__module__) != '.'.join(path):
                    continue

            # If this is a module, then things get complicated again and we
            # need to handle modules and packages differently. See also for
            # more info: https://stackoverflow.com/a/7948672
            else:
                # pybind11 submodules have __package__ set to None (instead of
                # '') for nested modules. Allow these. The parent's __package__
                # can be None (if it's a nested submodule), '' (if it's a
                # top-level module) or a string (if the parent is a Python
                # package), can't really check further.
                if state.config['PYBIND11_COMPATIBILITY'] and object.__package__ is None:
                    pass # yes, do nothing

                # The parent is a single-file module (not a package), these
                # don't have submodules so this is most definitely an imported
                # module. Source: https://docs.python.org/3/reference/import.html#packages
                elif not module.__package__: continue

                # The parent is a package and this is either a submodule or a
                # subpackage. Check that the __package__ of parent and child is
                # either the same or it's parent + child name
                elif object.__package__ not in [module.__package__, module.__package__ + '.' + name]: continue

            type = object_type(state, object)
            subpath = path + [name]

            # Crawl the submodules and subclasses recursively (they also add
            # itself to the name_map), add other members directly.
            if not type: # pragma: no cover
                # Ignore unknown object types (with __all__ we warn instead)
                continue
            elif type == EntryType.MODULE:
                submodules_to_crawl += [(subpath, object)]
                # Not adding to module_entry.members, done by the nested
                # crawl_module() itself if it is sure that it isn't a
                # duplicated module
                continue
            elif type == EntryType.CLASS:
                crawl_class(state, subpath, object)
            elif type == EntryType.ENUM:
                crawl_enum(state, subpath, object)
            else:
                assert type in [EntryType.FUNCTION, EntryType.DATA]
                entry = Empty()
                entry.type = type
                entry.object = object
                entry.path = subpath
                state.name_map['.'.join(subpath)] = entry

            module_entry.members += [name]

    # Add itself to the name map
    state.name_map['.'.join(path)] = module_entry

    return submodules_to_crawl

def make_relative_name(state: State, referrer_path: List[str], name):
    if name not in state.name_map: return name

    entry = state.name_map[name]

    # Strip common prefix from both paths. We always want to keep at least one
    # element from the entry path, so strip the last element off.
    common_prefix_length = len(os.path.commonprefix([referrer_path, entry.path[:-1]]))

    # Check for ambiguity of the shortened path -- for example, with referrer
    # being `module.sub.Foo`, target `module.Foo`, the path will get shortened
    # to `Foo`, making it seem like the target is `module.sub.Foo` instead of
    # `module.Foo`. To fix that, the shortened path needs to be `sub.Foo`
    # instead of `Foo`.
    def is_ambiguous(shortened_path):
        # Concatenate the shortened path with a prefix of the referrer path,
        # going from longest to shortest, until we find a name that exists. If
        # the first found name is the actual target, it's not ambiguous --
        # for example, linking from `module.sub` to `module.sub.Foo` can be
        # done just with `Foo` even though `module.Foo` exists as well, as it's
        # "closer" to the referrer.
        # TODO: See test cases in `inspect_type_links.first.Foo` for very
        #  *very* pathological cases where we're referencing `Foo` from
        # `module.Foo` and there's also `module.Foo.Foo`. Not sure which way is
        # better.
        for i in reversed(range(len(referrer_path))):
            potentially_ambiguous = referrer_path[:i] + shortened_path
            if '.'.join(potentially_ambiguous) in state.name_map:
                if potentially_ambiguous == entry.path: return False
                else: return True
        # the target *has to be* found
        assert False # pragma: no cover
    shortened_path = entry.path[common_prefix_length:]
    while common_prefix_length and is_ambiguous(shortened_path):
        common_prefix_length -= 1
        shortened_path = entry.path[common_prefix_length:]

    return '.'.join(shortened_path)

def make_name_link(state: State, referrer_path: List[str], type) -> str:
    if type is None: return None
    assert isinstance(type, str)

    # Not found, return as-is. However, if the prefix is one of the
    # INPUT_MODULES, emit a warning to notify the user of a potentially missing
    # stuff from the docs.
    if not type in state.name_map:
        for module in state.config['INPUT_MODULES']:
            if isinstance(module, str):
                module_name = module
            else:
                module_name = module.__name__
            if type.startswith(module_name + '.'):
                logging.warning("could not resolve a link to %s which is among INPUT_MODULES (referred from %s), possibly hidden/undocumented?", type, '.'.join(referrer_path))
                break
        return type

    # Make a shorter name that's relative to the referrer but still unambiguous
    relative_name = make_relative_name(state, referrer_path, type)

    # Format the URL
    entry = state.name_map[type]
    if entry.type == EntryType.CLASS:
        url = entry.url
    else:
        if entry.type == EntryType.ENUM:
            parent_index = -1
        else:
            assert entry.type == EntryType.ENUM_VALUE
            parent_index = -2
        parent_url = state.name_map['.'.join(entry.path[:parent_index])].url
        url = '{}#{}'.format(parent_url, state.config['ID_FORMATTER'](entry.type, entry.path[parent_index:]))

    return '<a href="{}" class="m-doc">{}</a>'.format(url, relative_name)

_pybind_name_rx = re.compile('[a-zA-Z0-9_]*')
_pybind_arg_name_rx = re.compile('[*a-zA-Z0-9_]+')
_pybind_type_rx = re.compile('[a-zA-Z0-9_.]+')
_pybind_default_value_rx = re.compile('[^,)]+')

def parse_pybind_type(state: State, referrer_path: List[str], signature: str) -> str:
    # If this doesn't match, it's because we're in Callable[[arg, ...], retval]
    match = _pybind_type_rx.match(signature)
    if match:
        input_type = match.group(0)
        signature = signature[len(input_type):]
        type = map_name_prefix(state, input_type)
        type_link = make_name_link(state, referrer_path, type)
    else:
        assert signature[0] == '['
        type = ''
        type_link = ''

    # This is a generic type (or the list in Callable)
    if signature and signature[0] == '[':
        type += '['
        type_link += '['
        signature = signature[1:]
        while signature[0] != ']':
            signature, inner_type, inner_type_link = parse_pybind_type(state, referrer_path, signature)
            type += inner_type
            type_link += inner_type_link

            if signature[0] == ']': break

            # Expecting the next item now, if not there, we failed
            if not signature.startswith(', '): raise SyntaxError()
            signature = signature[2:]

            type += ', '
            type_link += ', '

        assert signature[0] == ']'
        signature = signature[1:]
        type += ']'
        type_link += ']'

    return signature, type, type_link

# Returns function name, summary, list of arguments (name, type, type with HTML
# links, default value) and return type. If argument parsing failed, the
# argument list is a single "ellipsis" item.
def parse_pybind_signature(state: State, referrer_path: List[str], signature: str) -> Tuple[str, str, List[Tuple[str, str, str, str]], str]:
    original_signature = signature # For error reporting
    name = _pybind_name_rx.match(signature).group(0)
    signature = signature[len(name):]
    args = []
    assert signature[0] == '('
    signature = signature[1:]

    # parse_pybind_type() can throw a SyntaxError in case it gets confused,
    # provide graceful handling for that along with own parse errors
    try:
        # Arguments
        while signature[0] != ')':
            # Name
            arg_name = _pybind_arg_name_rx.match(signature).group(0)
            assert arg_name
            signature = signature[len(arg_name):]

            # Type (optional)
            if signature.startswith(': '):
                signature = signature[2:]
                signature, arg_type, arg_type_link = parse_pybind_type(state, referrer_path, signature)
            else:
                arg_type = None
                arg_type_link = None

            # Default (optional) -- for now take everything until the next comma
            # TODO: ugh, do properly
            # The equals has spaces around since 2.3.0, preserve 2.2 compatibility.
            # https://github.com/pybind/pybind11/commit/0826b3c10607c8d96e1d89dc819c33af3799a7b8
            if signature.startswith(('=', ' = ')):
                signature = signature[1 if signature[0] == '=' else 3:]
                default = _pybind_default_value_rx.match(signature).group(0)
                signature = signature[len(default):]
            else:
                default = None

            args += [(arg_name, arg_type, arg_type_link, default)]

            if signature[0] == ')': break

            # Expecting the next argument now, if not there, we failed
            if not signature.startswith(', '): raise SyntaxError()
            signature = signature[2:]

        assert signature[0] == ')'
        signature = signature[1:]

        # Return type (optional)
        if signature.startswith(' -> '):
            signature = signature[4:]
            signature, _, return_type_link = parse_pybind_type(state, referrer_path, signature)
        else:
            return_type_link = None

        # Expecting end of the signature line now, if not there, we failed
        if signature and signature[0] != '\n': raise SyntaxError()

    # Failed to parse, return an ellipsis and docs
    except SyntaxError:
        end = original_signature.find('\n')
        logging.warning("cannot parse pybind11 function signature %s", original_signature[:end if end != -1 else None])
        if end != -1 and len(original_signature) > end + 1 and original_signature[end + 1] == '\n':
            summary = take_first_paragraph(inspect.cleandoc(original_signature[end + 1:]))
        else:
            summary = ''
        return (name, summary, [('…', None, None, None)], None)

    if len(signature) > 1 and signature[1] == '\n':
        summary = take_first_paragraph(inspect.cleandoc(signature[2:]))
    else:
        summary = ''

    return (name, summary, args, return_type_link)

def parse_pybind_docstring(state: State, referrer_path: List[str], doc: str) -> List[Tuple[str, str, List[Tuple[str, str, str]], str]]:
    name = referrer_path[-1]

    # Multiple overloads, parse each separately
    overload_header = "{}(*args, **kwargs)\nOverloaded function.\n\n".format(name);
    if doc.startswith(overload_header):
        doc = doc[len(overload_header):]
        overloads = []
        id = 1
        while True:
            assert doc.startswith('{}. {}('.format(id, name))
            id = id + 1
            next = doc.find('{}. {}('.format(id, name))

            # Parse the signature and docs from known slice
            overloads += [parse_pybind_signature(state, referrer_path, doc[len(str(id - 1)) + 2:next])]
            assert overloads[-1][0] == name
            if next == -1: break

            # Continue to the next signature
            doc = doc[next:]

        return overloads

    # Normal function, parse and return the first signature
    else:
        return [parse_pybind_signature(state, referrer_path, doc)]

# Used to format function default arguments and data values. *Not* pybind's
# function default arguments, as those are parsed from a string representation.
def format_value(state: State, referrer_path: List[str], value: str) -> Optional[str]:
    if value is None: return str(value)
    if isinstance(value, enum.Enum):
        return make_name_link(state, referrer_path, '{}.{}.{}'.format(value.__class__.__module__, value.__class__.__qualname__, value.name))
    # pybind enums have the __members__ attribute instead. Since 2.3 pybind11
    # has .name like enum.Enum, but we still need to support 2.2 so hammer it
    # out of a str() instead.
    elif state.config['PYBIND11_COMPATIBILITY'] and hasattr(value.__class__, '__members__'):
        return make_name_link(state, referrer_path, '{}.{}.{}'.format(value.__class__.__module__, value.__class__.__qualname__, str(value).partition('.')[2]))
    elif '__repr__' in type(value).__dict__:
        # TODO: tuples of non-representable values will still be ugly
        return html.escape(repr(value))
    else:
        return None

def take_first_paragraph(doc: str) -> str:
    end = doc.find('\n\n')
    return doc if end == -1 else doc [:end]

def extract_summary(state: State, external_docs, path: List[str], doc: str) -> str:
    # Prefer external docs, if available
    path_str = '.'.join(path)
    if path_str in external_docs and external_docs[path_str]['summary']:
        return render_inline_rst(state, external_docs[path_str]['summary'])

    if not doc: return '' # some modules (xml.etree) have that :(
    # TODO: render as rst (config option for that)
    return html.escape(take_first_paragraph(inspect.cleandoc(doc)))

def extract_docs(state: State, external_docs, path: List[str], doc: str) -> Tuple[str, str]:
    path_str = '.'.join(path)
    if path_str in external_docs:
        external_doc_entry = external_docs[path_str]
    else:
        external_doc_entry = None

    # Summary. Prefer external docs, if available
    if external_doc_entry and external_doc_entry['summary']:
        summary = render_inline_rst(state, external_doc_entry['summary'])
    else:
        # some modules (xml.etree) have None as a docstring :(
        # TODO: render as rst (config option for that)
        summary = html.escape(take_first_paragraph(inspect.cleandoc(doc or '')))

    # Content
    if external_doc_entry and external_doc_entry['content']:
        content = render_rst(state, external_doc_entry['content'])
    else:
        # TODO: extract more than just a summary from the docstring
        content = None

    # Mark the docs as used (so it can warn about unused docs at the end)
    if external_doc_entry: external_doc_entry['used'] = True

    return summary, content

def extract_type(type) -> str:
    # For types we concatenate the type name with its module unless it's
    # builtins (i.e., we want re.Match but not builtins.int). We need to use
    # __qualname__ instead of __name__ because __name__ doesn't take nested
    # classes into account.
    return (type.__module__ + '.' if type.__module__ != 'builtins' else '') + type.__qualname__

def get_type_hints_or_nothing(state: State, path: List[str], object) -> Dict:
    # Calling get_type_hints on a pybind11 type (from extract_data_doc())
    # results in KeyError because there's no sys.modules['pybind11_builtins'].
    # Be pro-active and return an empty dict if that's the case.
    if state.config['PYBIND11_COMPATIBILITY'] and isinstance(object, type) and 'pybind11_builtins' in [a.__module__ for a in object.__mro__]:
        return {}

    try:
        return typing.get_type_hints(object)
    except Exception as e:
        # Gracefully handle an invalid name or a missing attribute, give up on
        # everything else (syntax error and so)
        if not isinstance(e, (AttributeError, NameError)): raise e
        logging.warning("failed to dereference type hints for %s (%s), falling back to non-dereferenced", '.'.join(path), e.__class__.__name__)
        return {}

def extract_annotation(state: State, referrer_path: List[str], annotation) -> str:
    # TODO: why this is not None directly?
    if annotation is inspect.Signature.empty: return None

    # If dereferencing with typing.get_type_hints() failed, we might end up
    # with forward-referenced types being plain strings. Keep them as is, since
    # those are most probably an error.
    if type(annotation) == str: return annotation

    # Or the plain strings might be inside (e.g. List['Foo']), which gets
    # converted by Python to ForwardRef. Hammer out the actual string and again
    # leave it as-is, since it's most probably an error.
    elif isinstance(annotation, typing.ForwardRef if sys.version_info >= (3, 7) else typing._ForwardRef):
        return annotation.__forward_arg__

    # Generic type names -- use their name directly
    elif isinstance(annotation, typing.TypeVar):
        return annotation.__name__

    # If the annotation is from the typing module, it ... gets complicated. It
    # could be a "bracketed" type, in which case we want to recurse to its
    # types as well.
    elif (hasattr(annotation, '__module__') and annotation.__module__ == 'typing'):
        # Optional or Union, handle those first
        if hasattr(annotation, '__origin__') and annotation.__origin__ is typing.Union:
            # FOR SOME REASON `annotation.__args__[1] is None` is always False
            if len(annotation.__args__) == 2 and isinstance(None, annotation.__args__[1]):
                name = 'typing.Optional'
                args = annotation.__args__[:1]
            else:
                name = 'typing.Union'
                args = annotation.__args__
        elif sys.version_info >= (3, 7) and hasattr(annotation, '_name') and annotation._name:
            name = 'typing.' + annotation._name
            # Any doesn't have __args__
            args = annotation.__args__ if hasattr(annotation, '__args__') else None
        # Python 3.6 has __name__ instead of _name
        elif sys.version_info < (3, 7) and hasattr(annotation, '__name__'):
            name = 'typing.' + annotation.__name__
            args = annotation.__args__
        # Any doesn't have __name__ in 3.6
        elif sys.version_info < (3, 7) and annotation is typing.Any:
            name = 'typing.Any'
            args = None
        # Whoops, something we don't know yet. Warn and return a string
        # representation at least.
        else: # pragma: no cover
            logging.warning("can't inspect annotation %s for %s, falling back to a string representation", annotation, '.'.join(referrer_path))
            return str(annotation)

        # Arguments of generic types, recurse inside
        if args:
            # For Callable, put the arguments into a nested list to separate
            # them from the return type
            if name == 'typing.Callable':
                assert len(args) >= 1
                return '{}[[{}], {}]'.format(name,
                    ', '.join([extract_annotation(state, referrer_path, i) for i in args[:-1]]),
                    extract_annotation(state, referrer_path, args[-1]))
            else:
                return '{}[{}]'.format(name, ', '.join([extract_annotation(state, referrer_path, i) for i in args]))
        else:
            return name

    # Things like (float, int) instead of Tuple[float, int] or using np.array
    # instead of np.ndarray. Ignore with a warning.
    elif not isinstance(annotation, type):
        logging.warning("invalid annotation %s in %s, ignoring", annotation, '.'.join(referrer_path))
        return None

    # Otherwise it's a plain type. Turn it into a link.
    return make_name_link(state, referrer_path, map_name_prefix(state, extract_type(annotation)))

def extract_module_doc(state: State, entry: Empty):
    assert inspect.ismodule(entry.object)

    out = Empty()
    out.url = entry.url
    out.name = entry.path[-1]
    out.summary = extract_summary(state, state.class_docs, entry.path, entry.object.__doc__)
    return out

def extract_class_doc(state: State, entry: Empty):
    assert inspect.isclass(entry.object)

    out = Empty()
    out.url = entry.url
    out.name = entry.path[-1]
    out.summary = extract_summary(state, state.class_docs, entry.path, entry.object.__doc__)
    return out

def extract_enum_doc(state: State, entry: Empty):
    out = Empty()
    out.name = entry.path[-1]
    out.id = state.config['ID_FORMATTER'](EntryType.ENUM, entry.path[-1:])
    out.values = []
    out.has_value_details = False

    # The happy case
    if issubclass(entry.object, enum.Enum):
        # Enum doc is by default set to a generic value. That's useless as well.
        if entry.object.__doc__ == 'An enumeration.':
            docstring = ''
        else:
            docstring = entry.object.__doc__
        out.summary, out.content = extract_docs(state, state.enum_docs, entry.path, docstring)
        out.has_details = bool(out.content)

        out.base = extract_type(entry.object.__base__)
        if out.base: out.base = make_name_link(state, entry.path, out.base)

        for i in entry.object:
            value = Empty()
            value.name = i.name
            value.id = state.config['ID_FORMATTER'](EntryType.ENUM_VALUE, entry.path[-1:] + [i.name])
            value.value = html.escape(repr(i.value))

            # Value doc gets by default inherited from the enum, that's useless
            if i.__doc__ == entry.object.__doc__:
                docstring = ''
            else:
                docstring = i.__doc__

            # TODO: external summary for enum values
            value.summary = extract_summary(state, {}, [], docstring)

            if value.summary:
                out.has_details = True
                out.has_value_details = True
            out.values += [value]

    # Pybind11 enums are ... different
    elif state.config['PYBIND11_COMPATIBILITY']:
        assert hasattr(entry.object, '__members__')

        out.summary, out.content = extract_docs(state, state.enum_docs, entry.path, entry.object.__doc__)
        out.has_details = bool(out.content)
        out.base = None

        for name, v in entry.object.__members__.items():
            value = Empty()
            value. name = name
            value.id = state.config['ID_FORMATTER'](EntryType.ENUM_VALUE, entry.path[-1:] + [name])
            value.value = int(v)
            # TODO: once https://github.com/pybind/pybind11/pull/1160 is
            #       released, extract from class docs (until then the class
            #       docstring is duplicated here, which is useless)
            # TODO: external summary for enum values
            value.summary = ''
            out.values += [value]

    if not state.config['SEARCH_DISABLED']:
        page_url = state.name_map['.'.join(entry.path[:-1])].url

        result = Empty()
        result.flags = ResultFlag.from_type(ResultFlag.NONE, EntryType.ENUM)
        result.url = '{}#{}'.format(page_url, out.id)
        result.prefix = entry.path[:-1]
        result.name = entry.path[-1]
        state.search += [result]

        for value in out.values:
            result = Empty()
            result.flags = ResultFlag.from_type(ResultFlag.NONE, EntryType.ENUM_VALUE)
            result.url = '{}#{}'.format(page_url, value.id)
            result.prefix = entry.path
            result.name = value.name
            state.search += [result]

    return out

def extract_function_doc(state: State, parent, entry: Empty) -> List[Any]:
    assert inspect.isfunction(entry.object) or inspect.ismethod(entry.object) or inspect.isroutine(entry.object)

    # Enclosing page URL for search
    if not state.config['SEARCH_DISABLED']:
        page_url = state.name_map['.'.join(entry.path[:-1])].url

    # Extract the signature from the docstring for pybind11, since it can't
    # expose it to the metadata: https://github.com/pybind/pybind11/issues/990
    # What's not solvable with metadata, however, are function overloads ---
    # one function in Python may equal more than one function on the C++ side.
    # To make the docs usable, list all overloads separately.
    #
    # Some shitty packages might be setting __doc__ to None (attrs is one of
    # them), explicitly check for that first.
    if state.config['PYBIND11_COMPATIBILITY'] and entry.object.__doc__ and entry.object.__doc__.startswith(entry.path[-1]):
        funcs = parse_pybind_docstring(state, entry.path, entry.object.__doc__)
        overloads = []
        for name, summary, args, type in funcs:
            out = Empty()
            out.name = entry.path[-1]
            out.params = []
            out.has_complex_params = False
            out.summary, out.content = extract_docs(state, state.function_docs, entry.path, summary)
            out.has_details = bool(out.content)

            # Don't show None return type for functions w/o a return
            out.type = None if type == 'None' else type
            if out.type: out.type = make_name_link(state, entry.path, out.type)

            # There's no other way to check staticmethods than to check for
            # self being the name of first parameter :( No support for
            # classmethods, as C++11 doesn't have that
            out.is_classmethod = False
            if inspect.isclass(parent) and args and args[0][0] == 'self':
                out.is_staticmethod = False
            else:
                out.is_staticmethod = True

            # Guesstimate whether the arguments are positional-only or
            # position-or-keyword. It's either all or none. This is a brown
            # magic, sorry.

            # For instance methods positional-only argument names are either
            # self (for the first argument) or arg(I-1) (for second
            # argument and further). Also, the `self` argument is
            # positional-or-keyword only if there are positional-or-keyword
            # arguments afgter it, otherwise it's positional-only.
            if inspect.isclass(parent) and not out.is_staticmethod:
                assert args and args[0][0] == 'self'

                positional_only = True
                for i, arg in enumerate(args[1:]):
                    name, type, type_link, default = arg
                    if name != 'arg{}'.format(i):
                        positional_only = False
                        break

            # For static methods or free functions positional-only arguments
            # are argI.
            else:
                positional_only = True
                for i, arg in enumerate(args):
                    name, type, type_link, default = arg
                    if name != 'arg{}'.format(i):
                        positional_only = False
                        break

            arg_types = []
            for i, arg in enumerate(args):
                name, type, type_link, default = arg
                param = Empty()
                param.name = name
                # Don't include redundant type for the self argument
                if name == 'self':
                    param.type = None
                    arg_types += [None]
                else:
                    param.type = type_link
                    arg_types += [type]
                if default:
                    # If the type is a registered enum, try to make a link to
                    # the value -- for an enum of type `module.EnumType`,
                    # assuming the default is rendered as `EnumType.VALUE` (not
                    # fully qualified), concatenate it together to have
                    # `module.EnumType.VALUE`
                    if type in state.name_map and state.name_map[type].type == EntryType.ENUM:
                        param.default = make_name_link(state, entry.path, '.'.join(state.name_map[type].path[:-1] + [default]))
                    else: param.default = html.escape(default)
                else:
                    param.default = None
                if type or default: out.has_complex_params = True

                # *args / **kwargs can still appear in the parsed signatures if
                # the function accepts py::args / py::kwargs directly
                if name == '*args':
                    param.name = 'args'
                    param.kind = 'VAR_POSITIONAL'
                elif name == '**kwargs':
                    param.name = 'kwargs'
                    param.kind = 'VAR_KEYWORD'
                else:
                    param.kind = 'POSITIONAL_ONLY' if positional_only else 'POSITIONAL_OR_KEYWORD'

                out.params += [param]

            # Format the anchor. Pybind11 functions are sometimes overloaded,
            # thus name alone is not enough.
            out.id = state.config['ID_FORMATTER'](EntryType.OVERLOADED_FUNCTION, entry.path[-1:] + arg_types)

            if not state.config['SEARCH_DISABLED']:
                result = Empty()
                result.flags = ResultFlag.from_type(ResultFlag.NONE, EntryType.FUNCTION)
                result.url = '{}#{}'.format(page_url, out.id)
                result.prefix = entry.path[:-1]
                result.name = entry.path[-1]
                result.params = []
                for i in range(len(out.params)):
                    param = out.params[i]
                    result.params += ['{}: {}'.format(param.name, make_relative_name(state, entry.path, arg_types[i])) if arg_types[i] else param.name]
                state.search += [result]

            overloads += [out]

        return overloads

    # Sane introspection path for non-pybind11 code
    else:
        out = Empty()
        out.name = entry.path[-1]
        out.id = state.config['ID_FORMATTER'](EntryType.FUNCTION, entry.path[-1:])
        out.params = []
        out.has_complex_params = False
        out.summary, out.content = extract_docs(state, state.function_docs, entry.path, entry.object.__doc__)
        out.has_details = bool(out.content)

        # Decide if classmethod or staticmethod in case this is a method
        if inspect.isclass(parent):
            out.is_classmethod = inspect.ismethod(entry.object)
            out.is_staticmethod = out.name in parent.__dict__ and isinstance(parent.__dict__[out.name], staticmethod)

        # First try to get fully dereferenced type hints (with strings
        # converted to actual annotations). If that fails (e.g. because a type
        # doesn't exist), we'll take the non-dereferenced annotations from
        # inspect instead.
        type_hints = get_type_hints_or_nothing(state, entry.path, entry.object)

        try:
            signature = inspect.signature(entry.object)

            if 'return' in type_hints:
                out.type = extract_annotation(state, entry.path, type_hints['return'])
            else:
                out.type = extract_annotation(state, entry.path, signature.return_annotation)
            for i in signature.parameters.values():
                param = Empty()
                param.name = i.name
                if i.name in type_hints:
                    param.type = extract_annotation(state, entry.path, type_hints[i.name])
                else:
                    param.type = extract_annotation(state, entry.path, i.annotation)
                if param.type:
                    out.has_complex_params = True
                if i.default is inspect.Signature.empty:
                    param.default = None
                else:
                    param.default = format_value(state, entry.path, i.default) or '…'
                    out.has_complex_params = True
                param.kind = str(i.kind)
                out.params += [param]

        # In CPython, some builtin functions (such as math.log) do not provide
        # metadata about their arguments. Source:
        # https://docs.python.org/3/library/inspect.html#inspect.signature
        except ValueError:
            param = Empty()
            param.name = '...'
            param.name_type = param.name
            out.params = [param]
            out.type = None

        if not state.config['SEARCH_DISABLED']:
            result = Empty()
            result.flags = ResultFlag.from_type(ResultFlag.NONE, EntryType.FUNCTION)
            result.url = '{}#{}'.format(page_url, out.id)
            result.prefix = entry.path[:-1]
            result.name = entry.path[-1]
            result.params = []
            state.search += [result]

        return [out]

def extract_property_doc(state: State, parent, entry: Empty):
    assert inspect.isdatadescriptor(entry.object)

    out = Empty()
    out.name = entry.path[-1]
    out.id = state.config['ID_FORMATTER'](EntryType.PROPERTY, entry.path[-1:])

    # If this is a slot, there won't be any fget / fset / fdel. Assume they're
    # gettable and settable (couldn't find any way to make them *inspectably*
    # readonly, all solutions involved throwing from __setattr__()) and
    # deletable as well (calling del on it seems to simply remove any
    # previously set value).
    # TODO: any better way to detect that those are slots?
    if entry.object.__class__.__name__ == 'member_descriptor' and entry.object.__class__.__module__ == 'builtins':
        out.is_gettable = True
        out.is_settable = True
        out.is_deletable = True
        # Unfortunately we can't get any docstring for these
        out.summary, out.content = extract_docs(state, state.property_docs, entry.path, '')
        out.has_details = bool(out.content)

        # First try to get fully dereferenced type hints (with strings
        # converted to actual annotations). If that fails (e.g. because a type
        # doesn't exist), we'll take the non-dereferenced annotations instead.
        type_hints = get_type_hints_or_nothing(state, entry.path, parent)

        if out.name in type_hints:
            out.type = extract_annotation(state, entry.path, type_hints[out.name])
        elif hasattr(parent, '__annotations__') and out.name in parent.__annotations__:
            out.type = extract_annotation(state, entry.path, parent.__annotations__[out.name])
        else:
            out.type = None

        return out

    # The properties can be defined using the low-level descriptor protocol
    # instead of the higher-level property() decorator. That means there's no
    # fget / fset / fdel, instead we need to look into __get__ / __set__ /
    # __delete__ directly. This is fairly rare (datetime.date is one and
    # BaseException.args is another I could find), so don't bother with it much
    # --- assume readonly and no docstrings / annotations whatsoever.
    if entry.object.__class__.__name__ == 'getset_descriptor' and entry.object.__class__.__module__ == 'builtins':
        out.is_gettable = True
        out.is_settable = False
        out.is_deletable = False
        # Unfortunately we can't get any docstring for these
        out.summary, out.content = extract_docs(state, state.property_docs, entry.path, '')
        out.has_details = bool(out.content)
        out.type = None
        return out

    out.is_gettable = entry.object.fget is not None
    if entry.object.fget or (entry.object.fset and entry.object.__doc__):
        docstring = entry.object.__doc__
    else:
        assert entry.object.fset
        docstring = entry.object.fset.__doc__
    out.summary, out.content = extract_docs(state, state.property_docs, entry.path, docstring)
    out.is_settable = entry.object.fset is not None
    out.is_deletable = entry.object.fdel is not None
    out.has_details = bool(out.content)

    # For the type, if the property is gettable, get it from getters's return
    # type. For write-only properties get it from setter's second argument
    # annotation.

    try:
        if entry.object.fget:
            signature = inspect.signature(entry.object.fget)

            # First try to get fully dereferenced type hints (with strings
            # converted to actual annotations). If that fails (e.g. because a
            # type doesn't exist), we'll take the non-dereferenced annotations
            # from inspect instead. This is deliberately done *after*
            # inspecting the signature because pybind11 properties would throw
            # TypeError from typing.get_type_hints(). This way they throw
            # ValueError from inspect and we don't need to handle TypeError in
            # get_type_hints_or_nothing().
            type_hints = get_type_hints_or_nothing(state, entry.path, entry.object.fget)

            if 'return' in type_hints:
                out.type = extract_annotation(state, entry.path, type_hints['return'])
            else:
                out.type = extract_annotation(state, entry.path, signature.return_annotation)
        else:
            assert entry.object.fset
            signature = inspect.signature(entry.object.fset)

            # Same as the lengthy comment above
            type_hints = get_type_hints_or_nothing(state, entry.path, entry.object.fset)

            # Get second parameter name, then try to fetch it from type_hints
            # and if that fails get its annotation from the non-dereferenced
            # version
            value_parameter = list(signature.parameters.values())[1]
            if value_parameter.name in type_hints:
                out.type = extract_annotation(state, entry.path, type_hints[value_parameter.name])
            else:
                out.type = extract_annotation(state, entry.path, value_parameter.annotation)

    except ValueError:
        # pybind11 properties have the type in the docstring
        if state.config['PYBIND11_COMPATIBILITY']:
            if entry.object.fget:
                out.type = parse_pybind_signature(state, entry.path, entry.object.fget.__doc__)[3]
            else:
                assert entry.object.fset
                parsed_args = parse_pybind_signature(state, entry.path, entry.object.fset.__doc__)[2]
                # If argument parsing failed, we're screwed
                if len(parsed_args) == 1: out.type = None
                else: out.type = parsed_args[1][2]
        else:
            out.type = None

    if not state.config['SEARCH_DISABLED']:
        result = Empty()
        result.flags = ResultFlag.from_type(ResultFlag.NONE, EntryType.PROPERTY)
        result.url = '{}#{}'.format(state.name_map['.'.join(entry.path[:-1])].url, out.id)
        result.prefix = entry.path[:-1]
        result.name = entry.path[-1]
        state.search += [result]

    return out

def extract_data_doc(state: State, parent, entry: Empty):
    assert not inspect.ismodule(entry.object) and not inspect.isclass(entry.object) and not inspect.isroutine(entry.object) and not inspect.isframe(entry.object) and not inspect.istraceback(entry.object) and not inspect.iscode(entry.object)

    out = Empty()
    out.name = entry.path[-1]
    out.id = state.config['ID_FORMATTER'](EntryType.DATA, entry.path[-1:])
    # Welp. https://stackoverflow.com/questions/8820276/docstring-for-variable
    out.summary, out.content = extract_docs(state, state.data_docs, entry.path, '')
    out.has_details = bool(out.content)

    # First try to get fully dereferenced type hints (with strings converted to
    # actual annotations). If that fails (e.g. because a type doesn't exist),
    # we'll take the non-dereferenced annotations instead.
    type_hints = get_type_hints_or_nothing(state, entry.path, parent)

    if out.name in type_hints:
        out.type = extract_annotation(state, entry.path, type_hints[out.name])
    elif hasattr(parent, '__annotations__') and out.name in parent.__annotations__:
        out.type = extract_annotation(state, entry.path, parent.__annotations__[out.name])
    else:
        out.type = None

    out.value = format_value(state, entry.path, entry.object)

    if not state.config['SEARCH_DISABLED']:
        result = Empty()
        result.flags = ResultFlag.from_type(ResultFlag.NONE, EntryType.DATA)
        result.url = '{}#{}'.format(state.name_map['.'.join(entry.path[:-1])].url, out.id)
        result.prefix = entry.path[:-1]
        result.name = entry.path[-1]
        state.search += [result]

    return out

def render(config, template: str, page, env: jinja2.Environment):
    template = env.get_template(template)
    rendered = template.render(page=page,
        URL=page.url,
        SEARCHDATA_FORMAT_VERSION=searchdata_format_version, **config)
    with open(os.path.join(config['OUTPUT'], page.filename), 'wb') as f:
        f.write(rendered.encode('utf-8'))
        # Add back a trailing newline so we don't need to bother with
        # patching test files to include a trailing newline to make Git
        # happy. Can't use keep_trailing_newline because that'd add it
        # also for nested templates :(
        f.write(b'\n')

def render_module(state: State, path, module, env):
    # Generate breadcrumb as the first thing as it generates the output
    # filename as a side effect
    breadcrumb = []
    filename: str
    url: str
    for i in range(len(path)):
        filename, url = state.config['URL_FORMATTER'](EntryType.MODULE, path[:i + 1])
        breadcrumb += [(path[i], url)]

    logging.debug("generating %s", filename)

    # Call all registered page begin hooks
    for hook in state.hooks_pre_page: hook()

    page = Empty()
    page.summary, page.content = extract_docs(state, state.module_docs, path, module.__doc__)
    page.filename = filename
    page.url = url
    page.breadcrumb = breadcrumb
    page.prefix_wbr = '.<wbr />'.join(path + [''])
    page.modules = []
    page.classes = []
    page.enums = []
    page.functions = []
    page.data = []
    page.has_enum_details = False
    page.has_function_details = False
    page.has_data_details = False

    # Find itself in the global map, save the summary back there for index
    module_entry = state.name_map['.'.join(path)]
    module_entry.summary = page.summary

    # Extract docs for all members
    for name in module_entry.members:
        subpath = path + [name]
        subpath_str = '.'.join(subpath)
        member_entry = state.name_map[subpath_str]

        if member_entry.type != EntryType.DATA and not object.__doc__: # pragma: no cover
            logging.warning("%s is undocumented", subpath_str)

        if member_entry.type == EntryType.MODULE:
            page.modules += [extract_module_doc(state, member_entry)]
        elif member_entry.type == EntryType.CLASS:
            page.classes += [extract_class_doc(state, member_entry)]
        elif member_entry.type == EntryType.ENUM:
            enum_ = extract_enum_doc(state, member_entry)
            page.enums += [enum_]
            if enum_.has_details: page.has_enum_details = True
        elif member_entry.type == EntryType.FUNCTION:
            functions = extract_function_doc(state, module, member_entry)
            page.functions += functions
            for function in functions:
                if function.has_details: page.has_function_details = True
        elif member_entry.type == EntryType.DATA:
            data = extract_data_doc(state, module, member_entry)
            page.data += [data]
            if data.has_details: page.has_data_details = True
        else: # pragma: no cover
            assert False

    if not state.config['SEARCH_DISABLED']:
        result = Empty()
        result.flags = ResultFlag.from_type(ResultFlag.NONE, EntryType.MODULE)
        result.url = page.url
        result.prefix = path[:-1]
        result.name = path[-1]
        state.search += [result]

    render(state.config, 'module.html', page, env)

def render_class(state: State, path, class_, env):
    # Generate breadcrumb as the first thing as it generates the output
    # filename as a side effect. It's a bit hairy because we need to figure out
    # proper entry type for the URL formatter for each part of the breadcrumb.
    breadcrumb = []
    filename: str
    url: str
    for i in range(len(path)):
        type = state.name_map['.'.join(path[:i + 1])].type
        filename, url = state.config['URL_FORMATTER'](type, path[:i + 1])
        breadcrumb += [(path[i], url)]

    logging.debug("generating %s", filename)

    # Call all registered page begin hooks
    for hook in state.hooks_pre_page: hook()

    page = Empty()
    page.summary, page.content = extract_docs(state, state.class_docs, path, class_.__doc__)
    page.filename = filename
    page.url = url
    page.breadcrumb = breadcrumb
    page.prefix_wbr = '.<wbr />'.join(path + [''])
    page.classes = []
    page.enums = []
    page.classmethods = []
    page.staticmethods = []
    page.dunder_methods = []
    page.methods = []
    page.properties = []
    page.data = []
    page.has_enum_details = False
    page.has_function_details = False
    page.has_property_details = False
    page.has_data_details = False

    # Find itself in the global map, save the summary back there for index
    module_entry = state.name_map['.'.join(path)]
    module_entry.summary = page.summary

    # Extract docs for all members
    for name in module_entry.members:
        subpath = path + [name]
        subpath_str = '.'.join(subpath)
        member_entry = state.name_map[subpath_str]

        # TODO: yell only if there's also no external doc content
        if member_entry.type != EntryType.DATA and not object.__doc__: # pragma: no cover
            logging.warning("%s is undocumented", subpath_str)

        if member_entry.type == EntryType.CLASS:
            page.classes += [extract_class_doc(state, member_entry)]
        elif member_entry.type == EntryType.ENUM:
            enum_ = extract_enum_doc(state, member_entry)
            page.enums += [enum_]
            if enum_.has_details: page.has_enum_details = True
        elif member_entry.type == EntryType.FUNCTION:
            for function in extract_function_doc(state, class_, member_entry):
                if name.startswith('__'):
                    page.dunder_methods += [function]
                elif function.is_classmethod:
                    page.classmethods += [function]
                elif function.is_staticmethod:
                    page.staticmethods += [function]
                else:
                    page.methods += [function]
                if function.has_details: page.has_function_details = True
        elif member_entry.type == EntryType.PROPERTY:
            property = extract_property_doc(state, class_, member_entry)
            page.properties += [property]
            if property.has_details: page.has_property_details = True
        elif member_entry.type == EntryType.DATA:
            data = extract_data_doc(state, class_, member_entry)
            page.data += [data]
            if data.has_details: page.has_data_details = True
        else: # pragma: no cover
            assert False

    if not state.config['SEARCH_DISABLED']:
        result = Empty()
        result.flags = ResultFlag.from_type(ResultFlag.NONE, EntryType.CLASS)
        result.url = page.url
        result.prefix = path[:-1]
        result.name = path[-1]
        state.search += [result]

    render(state.config, 'class.html', page, env)

# Extracts image paths and transforms them to just the filenames
class ExtractImages(Transform):
    # Max Docutils priority is 990, be sure that this is applied at the very
    # last
    default_priority = 991

    # There is no simple way to have stateful transforms (the publisher always
    # gets just the class, not the instance) so we have to use this
    # TODO: maybe the pending nodes could solve this?
    external_data = set()

    def __init__(self, document, startnode):
        Transform.__init__(self, document, startnode=startnode)

    def apply(self):
        ExtractImages._external_data = set()
        for image in self.document.traverse(docutils.nodes.image):
            # Skip absolute URLs
            if urllib.parse.urlparse(image['uri']).netloc: continue

            # TODO: is there a non-private access to current document source
            # path?
            ExtractImages._external_data.add(os.path.join(os.path.dirname(self.document.settings._source), image['uri']) if isinstance(self.document.settings._source, str) else image['uri'])

            # Patch the URL to be just the filename
            image['uri'] = os.path.basename(image['uri'])

class DocumentationWriter(m.htmlsanity.SaneHtmlWriter):
    def get_transforms(self):
        return m.htmlsanity.SaneHtmlWriter.get_transforms(self) + [ExtractImages]

def publish_rst(state: State, source, *, source_path=None, translator_class=m.htmlsanity.SaneHtmlTranslator):
    pub = docutils.core.Publisher(
        writer=DocumentationWriter(),
        source_class=docutils.io.StringInput,
        destination_class=docutils.io.StringOutput)
    pub.set_components('standalone', 'restructuredtext', 'html')
    pub.writer.translator_class = translator_class
    pub.process_programmatic_settings(None, m.htmlsanity.docutils_settings, None)
    # Docutils uses a deprecated U mode for opening files, so instead of
    # monkey-patching docutils.io.FileInput to not do that (like Pelican does),
    # I just read the thing myself.
    # TODO for external docs it *somehow* needs to supply the filename and line
    # range to it for better error reporting, this is too awful
    pub.set_source(source=source, source_path=source_path)
    pub.publish()

    # External images to pull later
    state.external_data = state.external_data.union(ExtractImages._external_data)

    return pub

def render_rst(state: State, source):
    return publish_rst(state, source, source_path=None).writer.parts.get('body').rstrip()

class _SaneInlineHtmlTranslator(m.htmlsanity.SaneHtmlTranslator):
    # Unconditionally force compact paragraphs. This means the inline HTML
    # won't be wrapped in a <p> which is exactly what we want.
    def should_be_compact_paragraph(self, node):
        return True

def render_inline_rst(state: State, source):
    return publish_rst(state, source, translator_class=_SaneInlineHtmlTranslator).writer.parts.get('body').rstrip()

def render_doc(state: State, filename):
    logging.debug("parsing docs from %s", filename)

    # Page begin hooks are called before this in run(), once for all docs since
    # these functions are not generating any pages

    # Render the file. The directives should take care of everything, so just
    # discard the output afterwards.
    with open(filename, 'r') as f: publish_rst(state, f.read())

def render_page(state: State, path, input_filename, env):
    filename, url = state.config['URL_FORMATTER'](EntryType.PAGE, path)

    logging.debug("generating %s", filename)

    # Call all registered page begin hooks
    for hook in state.hooks_pre_page: hook()

    # Render the file
    with open(input_filename, 'r') as f: pub = publish_rst(state, f.read(), source_path=input_filename)

    # Extract metadata from the page
    metadata = {}
    for docinfo in pub.document.traverse(docutils.nodes.docinfo):
        for element in docinfo.children:
            if element.tagname == 'field':
                name_elem, body_elem = element.children
                name = name_elem.astext()
                if name in state.config['FORMATTED_METADATA']:
                    # If the metadata are formatted, format them. Use a special
                    # translator that doesn't add <dd> tags around the content,
                    # also explicitly disable the <p> around as we not need it
                    # always.
                    # TODO: uncrapify this a bit
                    visitor = m.htmlsanity._SaneFieldBodyTranslator(pub.document)
                    visitor.compact_field_list = True
                    body_elem.walkabout(visitor)
                    value = visitor.astext()
                else:
                    value = body_elem.astext()
                metadata[name.lower()] = value

    # Breadcrumb, we don't do page hierarchy yet
    assert len(path) == 1
    breadcrumb = [(pub.writer.parts.get('title'), url)]

    page = Empty()
    page.filename = filename
    page.url = url
    page.breadcrumb = breadcrumb
    page.prefix_wbr = path[0]

    # Set page content and add extra metadata from there
    page.content = pub.writer.parts.get('body').rstrip()
    for key, value in metadata.items(): setattr(page, key, value)
    if not hasattr(page, 'summary'): page.summary = ''

    # Find itself in the global map, save the page title and summary back there
    # for index
    module_entry = state.name_map['.'.join(path)]
    module_entry.summary = page.summary
    module_entry.name = breadcrumb[-1][0]

    if not state.config['SEARCH_DISABLED']:
        result = Empty()
        result.flags = ResultFlag.from_type(ResultFlag.NONE, EntryType.PAGE)
        result.url = page.url
        result.prefix = path[:-1]
        result.name = path[-1]
        state.search += [result]

    render(state.config, 'page.html', page, env)

def is_html_safe(string):
    return '<' not in string and '>' not in string and '&' not in string and '"' not in string and '\'' not in string

def build_search_data(state: State, merge_subtrees=True, add_lookahead_barriers=True, merge_prefixes=True) -> bytearray:
    trie = Trie()
    map = ResultMap()

    symbol_count = 0
    for result in state.search:
        # Decide on prefix joiner
        if EntryType(result.flags.type) in [EntryType.MODULE, EntryType.CLASS, EntryType.FUNCTION, EntryType.PROPERTY, EntryType.ENUM, EntryType.ENUM_VALUE, EntryType.DATA]:
            joiner = '.'
        elif EntryType(result.flags.type) == EntryType.PAGE:
            joiner = ' » '
        else:
            assert False # pragma: no cover

        # Handle function arguments
        name_with_args = result.name
        name = result.name
        suffix_length = 0
        if hasattr(result, 'params') and result.params is not None:
            # Some very heavily annotated function parameters might cause the
            # suffix_length to exceed 256, which won't fit into the serialized
            # search data. However that *also* won't fit in the search result
            # list so there's no point in storing so much. Truncate it to 48
            # chars which should fit the full function name in the list in most
            # cases, yet be still long enough to be able to distinguish
            # particular overloads.
            # TODO: the suffix_length has to be calculated on UTF-8 and I
            # am (un)escaping a lot back and forth here -- needs to be
            # cleaned up
            params = ', '.join(result.params)
            if len(params) > 49:
                params = params[:48] + '…'
            name_with_args += '(' + params + ')'
            suffix_length += len(params.encode('utf-8')) + 2

        complete_name = joiner.join(result.prefix + [name_with_args])
        assert is_html_safe(complete_name) # this is not C++, so no <>&
        index = map.add(complete_name, result.url, suffix_length=suffix_length, flags=result.flags)

        # Add functions the second time with () appended, everything is the
        # same except for suffix length which is 2 chars shorter
        if hasattr(result, 'params') and result.params is not None:
            index_args = map.add(complete_name, result.url,
                suffix_length=suffix_length - 2, flags=result.flags)

        # Add the result multiple times with all possible prefixes
        prefixed_name = result.prefix + [name]
        for i in range(len(prefixed_name)):
            lookahead_barriers = []
            name = ''
            for j in prefixed_name[i:]:
                if name:
                    lookahead_barriers += [len(name)]
                    name += joiner
                name += html.unescape(j)
            trie.insert(name.lower(), index, lookahead_barriers=lookahead_barriers if add_lookahead_barriers else [])

            # Add functions the second time with () appended, referencing
            # the other result that expects () appended. The lookahead
            # barrier is at the ( character to avoid the result being shown
            # twice.
            if hasattr(result, 'params') and result.params is not None:
                trie.insert(name.lower() + '()', index_args, lookahead_barriers=lookahead_barriers + [len(name)] if add_lookahead_barriers else [])

        # Add this symbol to total symbol count
        symbol_count += 1

    # For each node in the trie sort the results so the found items have sane
    # order by default
    trie.sort(map)

    return serialize_search_data(trie, map, search_type_map, symbol_count, merge_subtrees=merge_subtrees, merge_prefixes=merge_prefixes)

def run(basedir, config, *, templates=default_templates, search_add_lookahead_barriers=True, search_merge_subtrees=True, search_merge_prefixes=True):
    # Populate the INPUT, if not specified, make it absolute
    if config['INPUT'] is None: config['INPUT'] = basedir
    else: config['INPUT'] = os.path.join(basedir, config['INPUT'])

    # Make the output dir absolute
    config['OUTPUT'] = os.path.join(config['INPUT'], config['OUTPUT'])
    if not os.path.exists(config['OUTPUT']): os.makedirs(config['OUTPUT'])

    # Guess MIME type of the favicon
    if config['FAVICON']:
        config['FAVICON'] = (config['FAVICON'], mimetypes.guess_type(config['FAVICON'])[0])

    state = State(config)

    # Prepare Jinja environment
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(templates), trim_blocks=True,
        lstrip_blocks=True, enable_async=True)
    # Filter to return file basename or the full URL, if absolute
    def basename_or_url(path):
        if urllib.parse.urlparse(path).netloc: return path
        return os.path.basename(path)
    # Filter to return URL for given symbol. If the path is a string, first try
    # to treat it as an URL -- either it needs to have the scheme or at least
    # one slash for relative links (in contrast, Python names don't have
    # slashes). If that fails,  turn it into a list and try to look it up in
    # various dicts.
    def path_to_url(path):
        if isinstance(path, str):
            if urllib.parse.urlparse(path).netloc or '/' in path: return path
            path = [path]
        entry = state.name_map['.'.join(path)]
        # TODO: this will blow up if linking to something that's not a module,
        # class or a page
        return state.config['URL_FORMATTER'](entry.type, entry.path)[1]

    env.filters['basename_or_url'] = basename_or_url
    env.filters['path_to_url'] = path_to_url
    env.filters['urljoin'] = urljoin

    # Set up extra plugin paths. The one for m.css plugins was added above.
    for path in config['PLUGIN_PATHS']:
        if path not in sys.path: sys.path.append(os.path.join(config['INPUT'], path))

    # Import plugins
    for plugin in ['m.htmlsanity'] + config['PLUGINS']:
        module = importlib.import_module(plugin)
        module.register_mcss(
            mcss_settings=config,
            jinja_environment=env,
            module_doc_contents=state.module_docs,
            class_doc_contents=state.class_docs,
            enum_doc_contents=state.enum_docs,
            function_doc_contents=state.function_docs,
            property_doc_contents=state.property_docs,
            data_doc_contents=state.data_docs,
            hooks_pre_page=state.hooks_pre_page,
            hooks_post_run=state.hooks_post_run)

    # Call all registered page begin hooks for the first time
    for hook in state.hooks_pre_page: hook()

    # Crawl all input modules to gather the name tree, put their names into a
    # list for the index. The crawl is done breadth-first, so the function
    # returns a list of submodules to be crawled next.
    class_index = []
    modules_to_crawl = []
    for module in config['INPUT_MODULES']:
        if isinstance(module, str):
            module_name = module
            module = importlib.import_module(module)
        else:
            module_name = module.__name__
        modules_to_crawl += [([module_name], module)]
        class_index += [module_name]
    while modules_to_crawl:
        path, object = modules_to_crawl.pop(0)
        if id(object) in state.crawled: continue
        modules_to_crawl += crawl_module(state, path, object)

    # Add special pages to the name map. The pages are done after so they can
    # override these.
    for page in special_pages:
        entry = Empty()
        entry.type = EntryType.SPECIAL
        entry.path = [page]
        state.name_map[page] = entry

    # Do the same for pages
    # TODO: turn also into some crawl_page() function? once we have subpages?
    page_index = []
    for page in config['INPUT_PAGES']:
        page_name = os.path.splitext(os.path.basename(page))[0]

        entry = Empty()
        entry.type = EntryType.PAGE
        entry.path = [page_name]
        entry.url = config['URL_FORMATTER'](EntryType.PAGE, [page_name])[1]
        entry.filename = os.path.join(config['INPUT'], page)
        state.name_map[page_name] = entry

        # The index page doesn't go to the index
        if page_name != 'index': page_index += [page_name]

    # Then process the doc input files so we have all data for rendering
    # module pages. This needs to be done *after* the initial crawl so
    # cross-linking works as expected.
    for file in config['INPUT_DOCS']:
        render_doc(state, os.path.join(basedir, file))

    # Go through all crawled names and render modules, classes and pages. A
    # side effect of the render is entry.summary (and entry.name for pages)
    # being filled.
    for entry in state.name_map.values():
        if entry.type == EntryType.MODULE:
            render_module(state, entry.path, entry.object, env)
        elif entry.type == EntryType.CLASS:
            render_class(state, entry.path, entry.object, env)
        elif entry.type == EntryType.PAGE:
            render_page(state, entry.path, entry.filename, env)

    # Warn if there are any unused contents left after processing everything
    for docs in ['module', 'class', 'enum', 'function', 'property', 'data']:
        unused_docs = [key for key, value in getattr(state, f'{docs}_docs').items() if not 'used' in value]
        if unused_docs:
            logging.warning("The following %s doc contents were unused: %s", docs, unused_docs)

    # Create module and class index from the toplevel name list. Recursively go
    # from the top-level index list and gather all class/module children.
    def fetch_class_index(entry):
        index_entry = Empty()
        index_entry.kind = 'module' if entry.type == EntryType.MODULE else 'class'
        index_entry.name = entry.path[-1]
        index_entry.url = state.config['URL_FORMATTER'](entry.type, entry.path)[1]
        index_entry.summary = entry.summary
        index_entry.has_nestable_children = False
        index_entry.children = []

        # Module children should go before class children, put them in a
        # separate list and then concatenate at the end
        class_children = []
        for member in entry.members:
            member_entry = state.name_map['.'.join(entry.path + [member])]
            if member_entry.type == EntryType.MODULE:
                index_entry.has_nestable_children = True
                index_entry.children += [fetch_class_index(state.name_map['.'.join(member_entry.path)])]
            elif member_entry.type == EntryType.CLASS:
                class_children += [fetch_class_index(state.name_map['.'.join(member_entry.path)])]
        index_entry.children += class_children

        return index_entry

    for i in range(len(class_index)):
        class_index[i] = fetch_class_index(state.name_map[class_index[i]])

    # Create page index from the toplevel name list
    # TODO: rework when we have nested page support
    for i in range(len(page_index)):
        entry = state.name_map[page_index[i]]
        assert entry.type == EntryType.PAGE

        index_entry = Empty()
        index_entry.kind = 'page'
        index_entry.name = entry.name
        index_entry.url = config['URL_FORMATTER'](entry.type, entry.path)[1]
        index_entry.summary = entry.summary
        index_entry.has_nestable_children = False
        index_entry.children = []

        page_index[i] = index_entry

    index = Empty()
    index.classes = class_index
    index.pages = page_index
    for file in special_pages[1:]: # exclude index
        template = env.get_template(file + '.html')
        filename, url = config['URL_FORMATTER'](EntryType.SPECIAL, [file])
        rendered = template.render(index=index, URL=url, **config)
        with open(os.path.join(config['OUTPUT'], filename), 'wb') as f:
            f.write(rendered.encode('utf-8'))
            # Add back a trailing newline so we don't need to bother with
            # patching test files to include a trailing newline to make Git
            # happy. Can't use keep_trailing_newline because that'd add it
            # also for nested templates :(
            f.write(b'\n')

    # Create index.html if it was not provided by the user
    if 'index.rst' not in [os.path.basename(i) for i in config['INPUT_PAGES']]:
        logging.debug("writing index.html for an empty main page")

        filename, url = config['URL_FORMATTER'](EntryType.SPECIAL, ['index'])

        page = Empty()
        page.filename = filename
        page.url = url
        page.breadcrumb = [(config['PROJECT_TITLE'], url)]
        render(config, 'page.html', page, env)

    if not state.config['SEARCH_DISABLED']:
        logging.debug("building search data for {} symbols".format(len(state.search)))

        data = build_search_data(state, add_lookahead_barriers=search_add_lookahead_barriers, merge_subtrees=search_merge_subtrees, merge_prefixes=search_merge_prefixes)

        if state.config['SEARCH_DOWNLOAD_BINARY']:
            with open(os.path.join(config['OUTPUT'], searchdata_filename), 'wb') as f:
                f.write(data)
        else:
            with open(os.path.join(config['OUTPUT'], searchdata_filename_b85), 'wb') as f:
                f.write(base85encode_search_data(data))

        # OpenSearch metadata, in case we have the base URL
        if state.config['SEARCH_BASE_URL']:
            logging.debug("writing OpenSearch metadata file")

            template = env.get_template('opensearch.xml')
            rendered = template.render(**state.config)
            output = os.path.join(config['OUTPUT'], 'opensearch.xml')
            with open(output, 'wb') as f:
                f.write(rendered.encode('utf-8'))
                # Add back a trailing newline so we don't need to bother with
                # patching test files to include a trailing newline to make Git
                # happy. Can't use keep_trailing_newline because that'd add it
                # also for nested templates :(
                f.write(b'\n')

    # Copy referenced files
    for i in config['STYLESHEETS'] + config['EXTRA_FILES'] + ([config['FAVICON'][0]] if config['FAVICON'] else []) + list(state.external_data) + ([] if config['SEARCH_DISABLED'] else ['search.js']):
        # Skip absolute URLs
        if urllib.parse.urlparse(i).netloc: continue

        # If file is found relative to the conf file, use that
        if os.path.exists(os.path.join(config['INPUT'], i)):
            i = os.path.join(config['INPUT'], i)

        # Otherwise use path relative to script directory
        else:
            i = os.path.join(os.path.dirname(os.path.realpath(__file__)), i)

        logging.debug("copying %s to output", i)
        shutil.copy(i, os.path.join(config['OUTPUT'], os.path.basename(i)))

    # Call all registered finalization hooks for the first time
    for hook in state.hooks_post_run: hook()

if __name__ == '__main__': # pragma: no cover
    parser = argparse.ArgumentParser()
    parser.add_argument('conf', help="configuration file")
    parser.add_argument('--templates', help="template directory", default=default_templates)
    parser.add_argument('--debug', help="verbose debug output", action='store_true')
    args = parser.parse_args()

    # Load configuration from a file, update the defaults with it
    config = copy.deepcopy(default_config)
    name, _ = os.path.splitext(os.path.basename(args.conf))
    module = SourceFileLoader(name, args.conf).load_module()
    if module is not None:
        config.update((k, v) for k, v in inspect.getmembers(module) if k.isupper())

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    run(os.path.dirname(os.path.abspath(args.conf)), config, templates=os.path.abspath(args.templates))
