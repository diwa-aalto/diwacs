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
    for extra in ["win32com.shell"]:
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

vspath = 'C:\\Program Files (x86)\\Microsoft Visual Studio 9.0\\VC\\redist\\'\
         'x86\\Microsoft.VC90.CRT'
sys.path.append(vspath)
mydata_content = ['data\\icon.ico']
x = glob('data\\*.png')
if x:
    for t in x:
        mydata_content.append(t)


setup(name="DiwaCS",
      options={'py2exe':
                    {'typelibs': [('{565783C6-CB41-11D1-8B02-00600806D9B6}',
                                   0, 1, 2)],
                    'bundle_files': 3,
                    'includes': ['zmq.utils.strtypes', 'zmq.utils.jsonapi',
                                  'zmq.core.pysocket', 'sqlalchemy',
                                  'sqlalchemy.dialects.mysql', 'pymysql',
                                  'PIL', 'pathtools', 'migrate', 'wmi',
                                  'migrate.changeset.databases.mysql'],
                     "packages": ['pubsub', 'zmq', 'configobj', 'migrate',
                                   'netifaces', 'lxml', 'pyaudio', 'wave',
                                   'wxversion'],
                     'dist_dir': 'wosdist',
                     "dll_excludes": ["libzmq.dll", "MPR.dll", "IPHLPAPI.dll"],
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
                  ("Microsoft.VC90.CRT", glob(vspath + r'\*.*')),
                  ("icons", glob(r'icons\*.*')),
                  #("migraterepo", glob(r'migraterepo\*.*')),
                  #("migraterepo\\versions", glob(r'migraterepo\\versions\*.*')
                  #("ofv", glob(r'ofv\*.*')),
                  #("rfv", glob(r'rfv\*.*')),
                  ("icons//filetypes", glob(r'icons\filetypes\*.*')),
                  ("data", mydata_content),
                  (".", ['C:\Users\Kristian\Documents\libzmq\libzmq.dll',
                         'logging.conf',
                         'config.ini'
                         ])
                 ]
)
