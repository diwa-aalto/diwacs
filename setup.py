"""
Created on 8.5.2012

:author: nick26

:synopsis:
    This file is used to compile a DiWaCS.exe file out of the python project
    using py2exe and setuptools packages available at:
    pypi.python.org/pypi/setuptools

"""
import sys
try:
    # py2exe 0.6.4 introduced a replacement modulefinder.
    # This means we have to add package paths there, not to the built-in
    # one.  If this new modulefinder gets integrated into Python, then
    # we might be able to revert this some day.
    # if this doesn't work, try import modulefinder
    try:
        import py2exe.mf as modulefinder
    except ImportError:
        import modulefinder
    import win32com
    for p in win32com.__path__[1:]:
        modulefinder.AddPackagePath('win32com', p)
    for extra in ['win32com.shell']:
        __import__(extra)
        m = sys.modules[extra]
        for p in m.__path__[1:]:
            modulefinder.AddPackagePath(extra, p)
except ImportError:
    # no build path setup, no worries.
    pass


from glob import glob
import os
import re
import traceback

from distutils.core import setup
from py2exe.build_exe import py2exe

LOGFILE = open('COMPILE.LOG', 'w')


class Py2ExeWithUPX(py2exe):
    """
    Custom py2exe distributer which packs all dll,pyd and exe files
    with upx before packaging.

    Class has been taken from:
    http://www.py2exe.org/index.cgi/BetterCompression

    And the original author of the class code is David Bolen.

    """

    UPX_CMD = r'C:\upx309w\upx.exe {0}'
    PYTHON_RE = re.compile(r'python[0-9]*\.dll')
    FILETYPES = ('.dll',)  # , '.pyd', '.exe')
    DEFAULT_OPTIONS = ('-1', '--compress-exports=0',
                       '--strip-relocs=0')

    def initialize_options(self):
        """DOCSTRING"""
        self.upx = False
        py2exe.initialize_options(self)

    def copy_file(self, *args, **kwargs):
        """DOCSTRING"""
        result = py2exe.copy_file(self, *args, **kwargs)

        # Process
        (filename, copied) = result
        filename = os.path.basename(filename).lower()
        (name, extension) = os.path.splitext(filename)
        LOGFILE.write(filename)

        # Helpers
        is_python = Py2ExeWithUPX.PYTHON_RE.match(filename) is not None
        is_packable = extension in Py2ExeWithUPX.FILETYPES
        LOGFILE.write(': {0} and {1} and {2} and not {3}\n'.\
                      format(copied, self.upx, is_packable, is_python))
        if (copied and self.upx and is_packable and not is_python):
            params = [s for s in Py2ExeWithUPX.DEFAULT_OPTIONS]
            params.append('"{0}"'.format(os.path.normpath(result[0])))
            params.append('>NUL')
            cmd = Py2ExeWithUPX.UPX_CMD.format(' '.join(params))
            os.system(cmd)
        return result

    def patch_python_dll_winver(self, dll_name, new_winver=None):
        """DOCSTRING"""
        if not self.dry_run:
#             query_params = ['-qt', '"{0}"'.format(dll_name), '>NUL']
#             cmd = Py2ExeWithUPX.UPX_CMD.format(' '.join(query_params))
#             cmd_result = os.system(cmd)
#             if not cmd_result:
#                 is_upxd = True
#             elif cmd_result == 2:
#                 is_upxd = False
#             else:
#                 raise IOError('UPX Analyising failed!')
#             if is_upxd:
#                 if self.verbose:
#                     template = 'Skipping winver patch for {0} (UPX\'d)'
#                     print template.format(dll_name)
#             else:
            py2exe.patch_python_dll_winver(self, dll_name, new_winver)
#                 if self.upx:
#                     params = [s for s in Py2ExeWithUPX.DEFAULT_OPTIONS]
#                     params.append('"{0}"'.format(os.path.normpath(dll_name)))
#                     params.append('>NULL')
#                     cmd = Py2ExeWithUPX.UPX_CMD.format(' '.join(params))
#                     os.system(cmd)


# --------------------------- EDIT BEGIN ------------------------------- #
VISUAL_STUDIO_PATH = (r'C:\Program Files (x86)\Microsoft Visual Studio 9.0\VC'
                      r'\redist\x86\Microsoft.VC90.CRT')

POSTGRESQL_PATH = r'C:\Program Files (x86)\PostgreSQL\9.2\lib'

OCI_PATH = r'C:\Program Files (x86)\OracleInstantClient'


MY_ICON = r'data\icon.ico'

TYPELIBS = [
    ('{565783C6-CB41-11D1-8B02-00600806D9B6}', 0, 1, 2)
]

INCLUDES = [
    'pymysql', 'PIL', 'pathtools', 'migrate', 'wmi',
    'migrate.changeset.databases.mysql', 'pyodbc', 'pg8000', 'urllib2',
    'pydoc_data', 'numpy'
]

EXCLUDES = [
    'tcl', 'Tkinter', 'Tkconstants', 'doctest'
]

PACKAGES = [
    'pubsub', 'zmq', 'configobj', 'migrate', 'lxml', 'pyaudio', 'wave',
    'wxversion', 'cffi', 'pycparser', 'sqlalchemy'
]

DLL_EXCLUDES = [
    'libzmq.dll', 'libpq.dll', 'MPR.dll', 'IPHLPAPI.dll', 'OCI.dll'
]

DATA_INCLUDES = [
    r'C:\Python27\Lib\site-packages\zmq\libzmq.dll', 'logging.conf',
    'config.ini'
]

DATA_ICONS = ('icons', glob(r'icons\*.*'))
DATA_FILETYPE_ICONS = ('icons/FILETYPES', glob(r'icons\FILETYPES\*.*'))

# ---------------------------- EDIT END -------------------------------- #


def main():
    """
    Main functionality of the setup script.

    Please give "py2exe" parameter for this one.

    Call it like this:
    `Python setup.py py2exe`

    """
    sys.path.append(VISUAL_STUDIO_PATH)
    sys.path.append(POSTGRESQL_PATH)
    #sys.path.append(ocipath)
    mydata_content = [MY_ICON]
    x = glob(r'data\*.png')
    if x:
        for t in x:
            mydata_content.append(t)

    options_py2exe = {
        'typelibs': TYPELIBS,
        'bundle_files': 1,
        'optimize': 2,
        # 'upx': True,
        'compressed': True,
        'includes': INCLUDES,
        'excludes': EXCLUDES,
        'packages': PACKAGES,
        'dist_dir': 'dist',
        'dll_excludes': DLL_EXCLUDES
    }

    window_diwacs = {
        'script': 'diwacs.py',
        'dest_base': 'DiwaCS',
        'icon_resources': [(0, MY_ICON)]
    }
    window_addfile = {'script': 'add_file.py'}
    window_sendfile = {'script': 'send_file_to.py'}
    window_manage = {'script': 'manage.py'}
    windows = [window_diwacs, window_addfile, window_sendfile, window_manage]

    data_files = [
        ('.', DATA_INCLUDES),
        ('data', mydata_content),
        DATA_ICONS,
        DATA_FILETYPE_ICONS
    ]
    options = {'py2exe': options_py2exe}
    cmdclass = {'py2exe': Py2ExeWithUPX}

    setup_params = {
        'name': 'DiWaCS',
        # 'cmdclass': cmdclass, # DOES NOT WORK ATM...
        'options': options,
        'windows': windows,
        'data_files': data_files,
        'zipfile': 'Diwa.lib'
    }

    setup(**setup_params)
    return 0


if __name__ == '__main__':
    value = 1
    try:
        value = main()
    except Exception as excp:
        print str(excp)
        traceback.print_tb(sys.exc_info()[2])
    LOGFILE.close()
    sys.exit(value)
else:
    LOGFILE.close()
