# Copyright 2015, Google Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#     * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""A setup module for the GRPC Python package."""

import os
import os.path
import platform
import shlex
import shutil
import sys
import sysconfig

from distutils import core as _core
from distutils import extension as _extension
import pkg_resources
import setuptools
from setuptools.command import egg_info

# Redirect the manifest template from MANIFEST.in to PYTHON-MANIFEST.in.
egg_info.manifest_maker.template = 'PYTHON-MANIFEST.in'

PY3 = sys.version_info.major == 3
PYTHON_STEM = './src/python/grpcio'
CORE_INCLUDE = ('./include', '.',)
BORINGSSL_INCLUDE = ('./third_party/boringssl/include',)
ZLIB_INCLUDE = ('./third_party/zlib',)

# Ensure we're in the proper directory whether or not we're being used by pip.
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(PYTHON_STEM))

# Break import-style to ensure we can actually find our in-repo dependencies.
import _unixccompiler_patch
import commands
import grpc_core_dependencies
import grpc_version

# TODO(atash) make this conditional on being on a mingw32 build
_unixccompiler_patch.monkeypatch_unix_compiler()


LICENSE = '3-clause BSD'

# Environment variable to determine whether or not the Cython extension should
# *use* Cython or use the generated C files. Note that this requires the C files
# to have been generated by building first *with* Cython support.
BUILD_WITH_CYTHON = os.environ.get('GRPC_PYTHON_BUILD_WITH_CYTHON', False)

# Environment variable to determine whether or not to enable coverage analysis
# in Cython modules.
ENABLE_CYTHON_TRACING = os.environ.get(
    'GRPC_PYTHON_ENABLE_CYTHON_TRACING', False)

# There are some situations (like on Windows) where CC, CFLAGS, and LDFLAGS are
# entirely ignored/dropped/forgotten by distutils and its Cygwin/MinGW support.
# We use these environment variables to thus get around that without locking
# ourselves in w.r.t. the multitude of operating systems this ought to build on.
# By default we assume a GCC-like compiler.
EXTRA_COMPILE_ARGS = shlex.split(os.environ.get('GRPC_PYTHON_CFLAGS', ''))
EXTRA_LINK_ARGS = shlex.split(os.environ.get('GRPC_PYTHON_LDFLAGS', ''))

CYTHON_EXTENSION_PACKAGE_NAMES = ()

CYTHON_EXTENSION_MODULE_NAMES = ('grpc._cython.cygrpc',)

CYTHON_HELPER_C_FILES = ()

CORE_C_FILES = tuple(grpc_core_dependencies.CORE_SOURCE_FILES)

EXTENSION_INCLUDE_DIRECTORIES = (
    (PYTHON_STEM,) + CORE_INCLUDE + BORINGSSL_INCLUDE + ZLIB_INCLUDE)

EXTENSION_LIBRARIES = ()
if "linux" in sys.platform:
  EXTENSION_LIBRARIES += ('rt',)
if not "win32" in sys.platform:
  EXTENSION_LIBRARIES += ('m',)
if "win32" in sys.platform:
  EXTENSION_LIBRARIES += ('ws2_32',)

DEFINE_MACROS = (('OPENSSL_NO_ASM', 1), ('_WIN32_WINNT', 0x600), ('GPR_BACKWARDS_COMPATIBILITY_MODE', 1),)
if "win32" in sys.platform:
  DEFINE_MACROS += (('OPENSSL_WINDOWS', 1), ('WIN32_LEAN_AND_MEAN', 1),)
  if '64bit' in platform.architecture()[0]:
    DEFINE_MACROS += (('MS_WIN64', 1),)

LDFLAGS = tuple(EXTRA_LINK_ARGS)
CFLAGS = tuple(EXTRA_COMPILE_ARGS)
if "linux" in sys.platform:
  LDFLAGS += ('-Wl,-wrap,memcpy',)
if "linux" in sys.platform or "darwin" in sys.platform:
  CFLAGS += ('-fvisibility=hidden',)

  pymodinit_type = 'PyObject*' if PY3 else 'void'

  pymodinit = '__attribute__((visibility ("default"))) {}'.format(pymodinit_type)
  DEFINE_MACROS += (('PyMODINIT_FUNC', pymodinit),)


# By default, Python3 distutils enforces compatibility of
# c plugins (.so files) with the OSX version Python3 was built with.
# For Python3.4, this is OSX 10.6, but we need Thread Local Support (__thread)
if 'darwin' in sys.platform and PY3:
  mac_target = sysconfig.get_config_var('MACOSX_DEPLOYMENT_TARGET')
  if mac_target and (pkg_resources.parse_version(mac_target) <
                     pkg_resources.parse_version('10.7.0')):
    os.environ['MACOSX_DEPLOYMENT_TARGET'] = '10.7'


def cython_extensions(module_names, extra_sources, include_dirs,
                      libraries, define_macros, build_with_cython=False):
  # Set compiler directives linetrace argument only if we care about tracing;
  # this is due to Cython having different behavior between linetrace being
  # False and linetrace being unset. See issue #5689.
  cython_compiler_directives = {}
  if ENABLE_CYTHON_TRACING:
    define_macros = define_macros + [('CYTHON_TRACE_NOGIL', 1)]
    cython_compiler_directives['linetrace'] = True
  file_extension = 'pyx' if build_with_cython else 'c'
  module_files = [os.path.join(PYTHON_STEM,
                               name.replace('.', '/') + '.' + file_extension)
                  for name in module_names]
  extensions = [
      _extension.Extension(
          name=module_name,
          sources=[module_file] + extra_sources,
          include_dirs=include_dirs, libraries=libraries,
          define_macros=define_macros,
          extra_compile_args=list(CFLAGS),
          extra_link_args=list(LDFLAGS),
      ) for (module_name, module_file) in zip(module_names, module_files)
  ]
  if build_with_cython:
    import Cython.Build
    return Cython.Build.cythonize(
        extensions,
        include_path=include_dirs,
        compiler_directives=cython_compiler_directives)
  else:
    return extensions

CYTHON_EXTENSION_MODULES = cython_extensions(
    list(CYTHON_EXTENSION_MODULE_NAMES),
    list(CYTHON_HELPER_C_FILES) + list(CORE_C_FILES),
    list(EXTENSION_INCLUDE_DIRECTORIES), list(EXTENSION_LIBRARIES),
    list(DEFINE_MACROS), bool(BUILD_WITH_CYTHON))

PACKAGE_DIRECTORIES = {
    '': PYTHON_STEM,
}

INSTALL_REQUIRES = (
    'six>=1.5.2',
    'enum34>=1.0.4',
    'futures>=2.2.0',
    # TODO(atash): eventually split the grpcio package into a metapackage
    # depending on protobuf and the runtime component (independent of protobuf)
    'protobuf>=3.0.0a3',
)

SETUP_REQUIRES = INSTALL_REQUIRES + (
    'sphinx>=1.3',
    'sphinx_rtd_theme>=0.1.8',
    'six>=1.10',
)

COMMAND_CLASS = {
    'doc': commands.SphinxDocumentation,
    'build_project_metadata': commands.BuildProjectMetadata,
    'build_py': commands.BuildPy,
    'build_ext': commands.BuildExt,
    'gather': commands.Gather,
}

# Ensure that package data is copied over before any commands have been run:
credentials_dir = os.path.join(PYTHON_STEM, 'grpc/_cython/_credentials')
try:
  os.mkdir(credentials_dir)
except OSError:
  pass
shutil.copyfile('etc/roots.pem', os.path.join(credentials_dir, 'roots.pem'))

PACKAGE_DATA = {
    # Binaries that may or may not be present in the final installation, but are
    # mentioned here for completeness.
    'grpc._cython': [
        '_credentials/roots.pem',
        '_windows/grpc_c.32.python',
        '_windows/grpc_c.64.python',
    ],
}
PACKAGES = setuptools.find_packages(PYTHON_STEM)

setuptools.setup(
  name='grpcio',
  version=grpc_version.VERSION,
  license=LICENSE,
  ext_modules=CYTHON_EXTENSION_MODULES,
  packages=list(PACKAGES),
  package_dir=PACKAGE_DIRECTORIES,
  package_data=PACKAGE_DATA,
  install_requires=INSTALL_REQUIRES,
  setup_requires=SETUP_REQUIRES,
  cmdclass=COMMAND_CLASS,
)
