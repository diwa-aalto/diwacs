"""
DiWaCS Variables
"""
import pyaudio
import os
import re
import sys

# A placeholder for default system cursor
DEFAULT_CURSOR = None

# A placeholder for blank cursor
BLANK_CURSOR = None

# Application name
APPLICATION_NAME = "DiWaCS"

# current application version
VERSION = "0.9.2.4"

# regex for URL parsing
URL_REGEX = re.compile(r'''((?:mailto:|ftp://|http://)[^ <>'"{}|\\^`[\]]*)''')

# System tray icon filename
TRAY_ICON = os.path.join("data", "Icon.png")

# Default screen icon filename
DEFAULT_SCREEN = os.path.join("data", "SCREEN.png")

# Empty screen icon filename
NO_SCREEN = os.path.join("data", "noscreen.png")

# The tooltip shown on systray hover
TRAY_TOOLTIP = ' '.join(("DiWaCS", VERSION,))

# The size of the main frame
FRAME_SIZE = (585, 170)

# The max number visible screens
MAX_SCREENS = 3

# Path of the config file. Users home directory/.wos
CONFIG_PATH = os.path.join(os.path.expanduser('~'), '.wos', "config.ini")

# A placeholder for configobj
CONFIG = None

# Does the application run shell commands if received any
RUN_CMD = False

# The location of the main server
STORAGE = ''

# The salt for the password
PASSWORD_SALT = "d1b729d398411d256ed1a092f88f4da4fbdaade6"

def UpdateStorage(storage):
    global STORAGE
    STORAGE = storage


# Current project information
CURRENT_PROJECT_PATH = None
CURRENT_PROJECT_ID = 0

# If debug mode is enable or not
DEBUG = False

# IS the input of the running computer being captured
CAPTURE = False

# The URL of the PAD file. For version checking purposes
PAD_URL = ''


def UpdatePadfile(padurl):
    global PAD_URL
    PAD_URL = padurl

# Is this application remote controlling some computer(s)
#CONTROLLING = False

# Is this computer being controlled by another application
#CONTROLLED = False

# Audio Recorder settings
FORMAT = pyaudio.paInt16
SHORT_NORMALIZE = (1.0 / 32768.0)
CHANNELS = 2
RATE = 44100
INPUT_BLOCK_TIME = 0.05
INPUT_FRAMES_PER_BLOCK = int(RATE * INPUT_BLOCK_TIME)
WINDOW_HEAD = 120
WINDOW_TAIL = 120
MAX_LENGTH = (WINDOW_HEAD + WINDOW_TAIL) / INPUT_BLOCK_TIME

# The version of windows OS
WINDOWS_MAJOR = 0
WINDOWS_MINOR = 0


def UpdateWindowsVersion():
    global WINDOWS_MAJOR, WINDOWS_MINOR
    WINDOWS_MAJOR = sys.getwindowsversion().major
    WINDOWS_MINOR = sys.getwindowsversion().minor


# PGM GROUP ADDRESS
PGM_GROUP = 1


def UpdatePGMGroup(new_group):
    global PGM_GROUP
    PGM_GROUP = new_group


# IP CAMERA VARS
CAMERA_URL = ''
CAMERA_USER = ''
CAMERA_PASS = ''


def UpdateCameraVars(url, user, passwd):
    global CAMERA_URL
    global CAMERA_USER
    global CAMERA_PASS
    if url:
        CAMERA_URL = url
    if user:
        CAMERA_USER = user
    if passwd:
        CAMERA_PASS = passwd


#Is audio recorded
AUDIO = False


def UpdateAudio(audio):
    global AUDIO
    AUDIO = audio

# If the node can act as RESPONSIVE.
# -1 Not Setup.
#  0 Will NOT act as responsive.
#  1 WILL act as responsive.
RESPONSIVE = -1


def UpdateResponsive(resp):
    global RESPONSIVE
    RESPONSIVE = resp


# DATABASE CONFIGS
DB_ADDRESS = ''
DB_NAME = ''
DB_TYPE = ''
DB_USER = ''
DB_PASS = ''
DB_DRIVER = {
             'mysql': 'pymysql',
             #'oracle': 'cx_oracle',
             'postgresql': 'pg8000',
             'mssql': 'pyodbc'
            }


def UpdateDatabase(ADDRESS=None, NAME=None, TYPE=None, USER=None, PASS=None):
    global DB_ADDRESS, DB_NAME, DB_TYPE, DB_USER, DB_PASS
    if ADDRESS:
        DB_ADDRESS = ADDRESS
    if NAME:
        DB_NAME = NAME
    if TYPE:
        DB_TYPE = TYPE
    if USER:
        DB_USER = USER
    if PASS:
        DB_PASS = PASS
