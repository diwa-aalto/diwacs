'''
Created on 8.5.2012

@author: nick26
'''
import sys
import wxversion
wxversion.select('2.9.4')
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
    for extra in ["win32com.shell"]: #,"win32com.mapi"
        __import__(extra)
        m = sys.modules[extra]
        for p in m.__path__[1:]:
            modulefinder.AddPackagePath(extra, p)
except ImportError:
    # no build path setup, no worries.
    pass
from distutils.core import setup
import py2exe
from glob import glob


setup(name="DiwaCS",
      options={'py2exe':
                    {"typelibs": [('{565783C6-CB41-11D1-8B02-00600806D9B6}',
                                   0, 1, 2)],
                    'bundle_files': 3,
                    'includes': ["zmq.utils.strtypes", "zmq.utils.jsonapi",
                                  "zmq.core.pysocket", 'sqlalchemy',
                                  'sqlalchemy.dialects.mysql', 'pymysql',
                                  'PIL', 'pathtools', 'migrate',
                                  'migrate.changeset.databases.mysql',
                                  'tempita', 'MySQLdb'],
                     "packages": ['pubsub', 'zmq', 'configobj', 'migrate',
                                   'tempita', 'MySQLdb', 'netifaces', 'lxml',
                                   'pyaudio', 'wave', 'wxversion'],
                     'dist_dir': 'wosdist',
                     "dll_excludes": ["libzmq.dll", "MPR.dll", "IPHLPAPI.dll"],
                     }
                 },
      windows=[
                {
                'script': "wos.py",
                'dest_base': 'DiwaCS',
                "icon_resources": [(0, "data\\icon.ico")]
                },
                {'script': "add_file.py"},
                {'script':'send_file_to.py'},
                {'script':'manage.py'}
              ],
      data_files=[
                  ("Microsoft.VC90.CRT", 
                   glob(r'C:\Program Files (x86)\Microsoft Visual Studio 9.0\VC\redist\x86\Microsoft.VC90.CRT\*.*')),
                  ("icons", glob(r'icons\*.*')),
                  #("migraterepo", glob(r'migraterepo\*.*')),
                  #("migraterepo\\versions", glob(r'migraterepo\\versions\*.*')),
                  #("ofv", glob(r'ofv\*.*')),
                  #("rfv", glob(r'rfv\*.*')),
                  #("7Zip64", glob(r'7Zip64\*.*')),
                  ("icons//filetypes", glob(r'icons\filetypes\*.*')),
                  (".", [
                         "data\\icon.ico",
                         'data\\Icon.png',
                         "data\\scr_mask.png",
                         "data\\scr_frame_mask.png",
                         "data\\SCREEN.png",
                         "data\\noscreen.png",
                         "C:\Users\\neriksso\zeromq-2.2.0\lib\libzmq.dll",
                         "logging.conf",
                         "data\\splashscreen.png",
                         "config.ini"
                        ]
                   )
                  ]
      )
