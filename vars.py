"""
DiWaCS Variables
"""
import re, pyaudio, os
# A placeholder for default system cursor
DEFAULT_CURSOR = None
# A placeholder for blank cursor
BLANK_CURSOR = None  
# Application name
APPLICATION_NAME = "DiWaCS"
# current application version
VERSION = "0.8.8"
# regex for URL parsing
URL_REGEX = re.compile(r'''((?:mailto:|ftp://|http://)[^ <>'"{}|\\^`[\]]*)''')
# System tray icon filename
TRAY_ICON = "Icon.png"
# Default screen icon filename
DEFAULT_SCREEN = "SCREEN.png"
# Empty screen icon filename
NO_SCREEN = "noscreen.png"
# The tooltip shown on systray hover
TRAY_TOOLTIP = ' '.join(("DiWaCS",VERSION,))
# The size of the main frame
FRAME_SIZE = (585,170)
# The max number visible screens
MAX_SCREENS = 3
# Path of the config file. Users home directory/.wos
CONFIG_PATH = os.path.join(os.path.expanduser('~'),'.wos',"config.ini")
# A placeholder for configobj
CONFIG = None
# Does the application run shell commands if received any
RUN_CMD = False
# The location of the main server
STORAGE = "192.168.1.10"
# Current project information
CURRENT_PROJECT_PATH = None
CURRENT_PROJECT_ID = 0
# If debug mode is enable or not
DEBUG = False
# IS the input of the running computer being captured
CAPTURE = False
# The URL of the PAD file. For version checking purposes
PAD_URL = "http://54.248.255.70/pad_file.xml"
# Is this application remote controlling some computer(s)
CONTROLLING = False
# Is this computer being controlled by another application
CONTROLLED = False
# Audio Recorder settings
FORMAT = pyaudio.paInt16 
SHORT_NORMALIZE = (1.0/32768.0)
CHANNELS = 2
RATE = 44100  
INPUT_BLOCK_TIME = 0.05
INPUT_FRAMES_PER_BLOCK = int(RATE*INPUT_BLOCK_TIME)
WINDOW_HEAD = 120
WINDOW_TAIL = 120
MAX_LENGTH = (WINDOW_HEAD + WINDOW_TAIL)/INPUT_BLOCK_TIME
# The version of windows OS
WINDOWS_MAJOR = 6
# PGM GROUP ADDRESS
PGM_GROUP = 1
# IP CAMERA VARS
CAMERA_URL = "http://192.168.1.85/image/jpeg.cgi"
CAMERA_USER = "admin"
CAMERA_PASS = "wosadmin"
#Is audi orecorded
AUDIO = False
# If the node can act as RESPONSIVE. 
# -1 Not Setup
#  0 Will NOT act as responsive
#  1 WILL act as responsive 
RESPONSIVE = -1