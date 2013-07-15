"""
DiWaCS Variables

"""
import pyaudio
import os
import re
import sys
from win32con import VK_LWIN, VK_ESCAPE


# A placeholder for default system cursor
DEFAULT_CURSOR = None


def set_default_cursor(value):
    """
    Set the default cursor variable.

    """
    global DEFAULT_CURSOR
    DEFAULT_CURSOR = value


# A placeholder for blank cursor
BLANK_CURSOR = None


def set_blank_cursor(value):
    """
    Set the blank cursor variable.

    """
    global BLANK_CURSOR
    BLANK_CURSOR = value


# Application name
APPLICATION_NAME = 'DiWaCS'

# current application version
VERSION = '0.9.3.0'

# regex for URL parsing
URL_REGEX = re.compile(r'''((?:mailto:|ftp://|http://)[^ <>'"{}|\\^`[\]]*)''')

# System tray icon filename
TRAY_ICON = os.path.join('data', 'Icon.png')

# Default screen icon filename
DEFAULT_SCREEN = os.path.join('data', 'SCREEN.png')

# Empty screen icon filename
NO_SCREEN = os.path.join('data', 'noscreen.png')

# Splash screen
SPLASH_SCREEN = os.path.join('data', 'splashscreen.png')

# The tooltip shown on systray hover
TRAY_TOOLTIP = '%s %s' % (APPLICATION_NAME, VERSION)

# The size of the main frame
FRAME_SIZE = (585, 170)

# The max number visible screens
MAX_SCREENS = 3

# Path of the config file. Users home directory/.wos
CONFIG_PATH = os.path.join(os.path.expanduser('~'), '.wos', "config.ini")

# A placeholder for configobj
CONFIG = None


def set_config(config):
    """ Set the CONFIG global... """
    global CONFIG
    CONFIG = config


# Currently running (not a dry-import)
CURRENTLY_RUNNING = False


def set_running():
    """
    Set the currently running flag as true.

    Causes other modules to redirect their stdout and stderr streams
    to files.

    """
    global CURRENTLY_RUNNING
    CURRENTLY_RUNNING = True


# Logger initializers.
LOGGER_INITIALIZER_LIST = []


def add_logger_initializer(logger_initializer):
    """
    For initializing the loggers from main.

    :param logger_initializer:
        The logger initializer to add to initialize chain.
    :type logger_initializer: function

    """
    if LOGGER_INITIALIZER_LIST.count(logger_initializer) < 1:
        LOGGER_INITIALIZER_LIST.append(logger_initializer)


# Logger level setters.
LOGGER_LEVEL_SETTER_LIST = []


def add_logger_level_setter(logger_level_setter):
    """
    For setting application logger level globally.

    :param logger_level_setter:
        The logger level setter to add to level set chain.
    :type logger_level_setter: function

    """
    if LOGGER_LEVEL_SETTER_LIST.count(logger_level_setter) < 1:
        LOGGER_LEVEL_SETTER_LIST.append(logger_level_setter)


# Does the application run shell commands if received any
RUN_CMD = False


def set_run_cmd(value):
    """
    Update the RUN_CMD setting.

    :param value: Desired value.
    :type value: Boolean

    """
    global RUN_CMD
    RUN_CMD = value


KEY_MODIFIER = VK_LWIN
KEY = VK_ESCAPE


def update_keys(modifier=VK_LWIN, key=VK_ESCAPE):
    """
    Update the key combination to stop remote controlling.

    :param modifier: The key to hold.
    :type modifier: Integer

    :param key: The key to press while holding modifier key.
    :type key: Integer

    """
    global KEY_MODIFIER, KEY
    KEY_MODIFIER = modifier
    KEY = key


# The location of the main server
STORAGE = ''
PROJECT_PATH = ''


def update_storage(storage):
    """
    Update the address of storage.

    :param storage: The new address of storage.
    :type storage: String

    """
    global STORAGE, PROJECT_PATH
    STORAGE = storage
    PROJECT_PATH = os.path.join(r'\\' + STORAGE, 'Projects')


# The salt for the password
PASSWORD_SALT = 'd1b729d398411d256ed1a092f88f4da4fbdaade6'
PASSWORD_ITERATIONS = 101

# If debug mode is enable or not
DEBUG = False

# IS the input of the running computer being captured
CAPTURE = False

# The URL of the PAD file. For version checking purposes
PAD_URL = ''


def update_padfile(padurl):
    """
    Set the padfile address.

    """
    global PAD_URL
    PAD_URL = padurl

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


def update_windows_version():
    """
    Updates the current version information to variables:
        - WINDOWS_MAJOR
        - WINDOWS_MINOR

    """
    global WINDOWS_MAJOR, WINDOWS_MINOR
    WINDOWS_MAJOR = sys.getwindowsversion().major
    WINDOWS_MINOR = sys.getwindowsversion().minor


update_windows_version()


# PGM GROUP ADDRESS
PGM_GROUP = 1


def update_PGM_group(new_group):
    """
    Update the PGM group for this node.

    """
    global PGM_GROUP
    PGM_GROUP = new_group


# IP CAMERA VARS
CAMERA_URL = ''
CAMERA_USER = ''
CAMERA_PASS = ''


def update_camera_vars(url, user, passwd):
    """
    Docstring here.

    """
    global CAMERA_URL, CAMERA_USER, CAMERA_PASS
    if url:
        CAMERA_URL = url
    if user:
        CAMERA_USER = user
    if passwd:
        CAMERA_PASS = passwd


# Is audio recorded
AUDIO = False


def update_audio(audio):
    """
    Docstring here.

    """
    global AUDIO
    AUDIO = audio


# If the node can act as RESPONSIVE.
# -1 Not Setup.
#  0 Will NOT act as responsive.
#  Same as PGM_Group WILL act as responsive.
RESPONSIVE = -1


def update_responsive(resp):
    """
    Docstring here.

    """
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
DB_STRING = ''


def update_database_vars(address=None, name=None, type_=None, user=None,
                         password=None):
    """
    Docstring here.

    """
    global DB_ADDRESS, DB_NAME, DB_TYPE, DB_USER, DB_PASS, DB_STRING
    __myformat = '%s+%s://%s:%s@%s/%s?charset=utf8&use_unicode=1'
    if address:
        DB_ADDRESS = address
    if name:
        DB_NAME = name
    if type_:
        DB_TYPE = type_
    if user:
        DB_USER = user
    if password:
        DB_PASS = password
    if DB_ADDRESS and DB_NAME and DB_TYPE and DB_USER and DB_PASS:
        db_driver = DB_DRIVER[DB_TYPE] if DB_TYPE in DB_DRIVER else ''
        if not db_driver:
            return
        DB_STRING = __myformat % (DB_TYPE, db_driver, DB_USER, DB_PASS,
                                  DB_ADDRESS, DB_NAME)
