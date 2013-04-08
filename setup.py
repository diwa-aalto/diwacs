'''
Created on 6.5.2012

@author: nick26
'''
from distutils.core import setup
import py2exe
from glob import glob 
setup(name="WOS",
       options = {'py2exe': {'optimize': 2,'bundle_files': 2,"compressed": 1,'includes':["zmq.utils.strtypes", "zmq.utils.jsonapi","zmq.core.pysocket",],"packages": ['pubsub'], }},
      windows=[{'script': "gui.py", }],
      data_files=[("Microsoft.VC90.CRT", glob(r'C:\Program Files\Microsoft Visual Studio 9.0\VC\redist\x86\Microsoft.VC90.CRT\*.*')),
                  (".",
                   ["icon.ico","SCREEN.png"]) ],
      #zipfile = None,
)