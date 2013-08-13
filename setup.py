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


from distutils.core import setup
import py2exe  # @UnusedImport
from glob import glob

vspath = 'C:\\Program Files (x86)\\Microsoft Visual Studio 9.0\\VC\\redist\\'\
         'x86\\Microsoft.VC90.CRT'
postgrepath = 'C:\\Program Files (x86)\\PostgreSQL\\9.2\\lib'
#ocipath = r'C:\Program Files (x86)\OracleInstantClient'
sys.path.append(vspath)
sys.path.append(postgrepath)
#sys.path.append(ocipath)
mydata_content = [r'data\icon.ico']
x = glob(r'data\*.png')
if x:
    for t in x:
        mydata_content.append(t)

options_py2exe_typelibs = [('{565783C6-CB41-11D1-8B02-00600806D9B6}', 0, 1, 2)]
options_py2exe_includes = ['pymysql', 'PIL', 'pathtools', 'migrate', 'wmi',
                           'migrate.changeset.databases.mysql', 'pyodbc',
                           'pg8000']
options_py2exe_packages = ['pubsub', 'zmq', 'configobj', 'migrate', 'lxml',
                           'pyaudio', 'wave', 'wxversion', 'cffi', 'pycparser',
                           'sqlalchemy']
options_py2exe_dll_excludes = ['libzmq.dll', 'libpq.dll', 'MPR.dll',
                               'IPHLPAPI.dll', 'OCI.dll']

options_py2exe = {
                  'typelibs': options_py2exe_typelibs,
                  'bundle_files': 1,
                  'optimize': 2,
                  'compressed': True,
                  'includes': options_py2exe_includes,
                  'packages': options_py2exe_packages,
                  'dist_dir': 'dist',
                  'dll_excludes': options_py2exe_dll_excludes
                  }

options = {'py2exe': options_py2exe}


window_diwacs = {
                 'script': 'diwacs.py',
                 'dest_base': 'DiwaCS',
                 'icon_resources': [(0, r'data\icon.ico')]
                 }
window_addfile = {'script': 'add_file.py'}
window_sendfile = {'script': 'send_file_to.py'}
window_manage = {'script': 'manage.py'}

windows = [window_diwacs, window_addfile, window_sendfile, window_manage]


templist = [r'C:\Python27\Lib\site-packages\zmq\libzmq.dll', 'logging.conf',
            'config.ini']

data_files = []
data_files.append(('icons', glob(r'icons\*.*')))
data_files.append(('icons/filetypes', glob(r'icons\filetypes\*.*')))
data_files.append(('data', mydata_content))
data_files.append(('.', templist))

setup(name="DiwaCS", options=options, windows=windows, data_files=data_files,
      zipfile='Diwa.lib')
