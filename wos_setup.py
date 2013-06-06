"""
Created on 8.5.2012

@author: nick26

tldalsdkasdlakd

:synopsis: \
    This file is used to compile a DiWaCS.exe file out of the python project
    using py2exe and setuptools packages available at:
    pypi.python.org/pypi/setuptools

"""
import sys
#import wxversion
#wxversion.select('2.9.4')
# ModuleFinder can't handle runtime changes to __path__, but win32com uses them
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
        modulefinder.AddPackagePath("win32com", p)
    for extra in ["win32com.shell"]:
        __import__(extra)
        m = sys.modules[extra]
        for p in m.__path__[1:]:
            modulefinder.AddPackagePath(extra, p)
except ImportError:
    # no build path setup, no worries.
    pass

"""
    Currently we are breaking this note, consider removing wxversion select.

    NOTE: If you are making a 'bundle' of your application with a tool
    like py2exe then you should *not* use the wxversion module since it
    looks at the filesystem for the directories on sys.path, it will fail
    in a bundled environment.  Instead you should simply ensure that
     the
    version of wxPython that you want is found by default on the sys.
     path
    when making the bundled version by setting PYTHONPATH.  Then
     that
    version will be included in your bundle and your app will work as
    expected.  Py2exe and the others usually have a way to tell at
     runtime
    if they are running from a bundle or running raw, so you can check
    that and only use wxversion if needed.
"""

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
mydata_content = ['data\\icon.ico']
x = glob('data\\*.png')
if x:
    for t in x:
        mydata_content.append(t)


setup(name="DiwaCS",
      options={'py2exe':
                    {'typelibs': [('{565783C6-CB41-11D1-8B02-00600806D9B6}',
                                   0, 1, 2)],
                    'bundle_files': 1,
                    'optimize': 2,
                    'compressed': True,
                    'includes': ['pymysql', 'PIL', 'pathtools', 'migrate',
                                 'wmi', 'migrate.changeset.databases.mysql',
                                 'pyodbc', 'pg8000'],
                     "packages": ['pubsub', 'zmq', 'configobj', 'migrate',
                                   'lxml', 'pyaudio', 'wave', 'wxversion',
                                   'cffi', 'pycparser', 'sqlalchemy'],
                     'dist_dir': 'wosdist',
                     "dll_excludes": ["libzmq.dll", "libpq.dll", "MPR.dll",
                                      "IPHLPAPI.dll", "OCI.dll"],
                     }
                 },
      windows=[
                {
                'script': "wos.py",
                'dest_base': 'DiwaCS',
                "icon_resources": [(0, r'data\icon.ico')]
                },
                {'script': 'add_file.py'},
                {'script': 'send_file_to.py'},
                {'script': 'manage.py'}
              ],
      data_files=[
                  # ("Microsoft.VC90.CRT", glob(vspath + r'\*.*')),
                  ("icons", glob(r'icons\*.*')),
                  # ("migraterepo", glob(r'migraterepo\*.*')),
                  #("migraterepo\\versions", glob(r'migraterepo\\versions\*.*')
                  # ("ofv", glob(r'ofv\*.*')),
                  # ("rfv", glob(r'rfv\*.*')),
                  ("icons/filetypes", glob(r'icons\filetypes\*.*')),
                  ("data", mydata_content),
                  (".", [r'C:\Python27\Lib\site-packages\zmq\libzmq.dll',
                         'logging.conf',
                         'config.ini'
                         ])
                 ],
      zipfile='diwa.lib'
)
