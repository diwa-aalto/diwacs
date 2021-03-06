"""
Created on 17.5.2013

:author: neriksso

"""
# System imports.
import datetime
from logging import config, getLogger
import os
import shutil
import subprocess
import tempfile
from _winreg import (OpenKey, CloseKey, HKEY_CURRENT_USER, QueryValueEx)
import xmlrpclib

# 3rd party imports.
from PIL import Image, ImageOps, ImageGrab


# Own imports.
import controller
import diwavars
from models import Project


LOGGER = None


def __init_logger():
    """
    Used to initialize the logger, when running from diwacs.py

    """
    global LOGGER
    config.fileConfig('logging.conf')
    LOGGER = getLogger('filesystem')


def __set_logger_level(level):
    """
    Sets the logger level for filesystem logger.

    :param level: Level of logging.
    :type level: Integer

    """
    LOGGER.setLevel(level)

# TODO: Map when copy_file_to_project and copy_to_temporary_directory are called.
diwavars.add_logger_initializer(__init_logger)
diwavars.add_logger_level_setter(__set_logger_level)


def copy_file_to_project(filepath, project_id):
    """
    Copy file to project dir and return new filepath in project directory.

    :param filepath: The file path.
    :type filepath: String

    :param project_id: Project id from database.
    :type project_id: Integer

    :returns: The path for this file in project directory or empty string.
    :rtype: String

    """
    project_path = Project.get_by_id(project_id).dir
    file_project_path = search_file(os.path.basename(filepath), project_path)
    if file_project_path:
        return file_project_path
    result = ''
    try:
        shutil.copy2(filepath, project_path)
        result = os.path.join(project_path, os.path.basename(filepath))
    except (ValueError, IOError, OSError):
        LOGGER.exception('File copy error')
    return result


def copy_to_temporary_directory(filepath):
    """Copy a file to temporary folder.

    :param filepath: The file path.
    :type filepath: String

    """
    result = ''
    try:
        temp_path = os.path.join(diwavars.PROJECT_PATH, 'temp')
        if not os.path.exists(temp_path):
            os.makedirs(temp_path)
        extension = get_file_extension(filepath)
        (fd, destination) = tempfile.mkstemp(dir=temp_path, suffix=extension)
        os.close(fd)
        shutil.copy(filepath, destination)
        result = destination
    except (ValueError, IOError, OSError):
        pass
    return result


def create_project_directory(dir_name):
    """
    Creates a project directory, if one does not exist in the file system

    :param dir_name: Name of the directory
    :type dir_name: String

    """
    project_dir = os.path.join(diwavars.PROJECT_PATH, unicode(dir_name))
    try:
        if not os.path.exists(project_dir):
            os.makedirs(project_dir)
        return project_dir
    except (ValueError, IOError, OSError):
        LOGGER.exception('Error creating project dir.')
        return ''


def delete_directory(path):
    """
    Deletes a directory.

    :returns: Weather the function was successful or not.
    :rtype: String

    """
    result = False
    try:
        shutil.rmtree(path)
        result = True
    except (ValueError, IOError, OSError):
        LOGGER.exception('Delete dir exception.')
    return result


# Module global constants.
__WIN_XP_REG = r'Software\Microsoft\Windows\CurrentVersion\Themes\LastTheme'
__WIN_VISTA7_REG = r'Control Panel\Desktop'


def get_current_wallpaper(win):
    """
    Try to get the current wallpaper image path.

    :param win: Windows version (Major, Minor).
    :type win: Tuple of Integers

    :returns: Wallpaper image path if it can find it.
    :rtype: String

    """
    wallpaper = None
    wallpaper_path = ''
    key = None
    default_entry = None
    reg_location = None
    LOGGER.debug('get_current_wallpaper: ' + str(win))
    if win[0] == 5:  # XP == 5,1    XP64 == 5,2
        reg_location = __WIN_XP_REG
    elif win[0] == 6:
        reg_location = __WIN_VISTA7_REG
        if win[1] == 0:  # Vista
            default_entry = r'Microsoft\Windows\Themes\TranscodedWallpaper.jpg'
        elif win[1] == 1:  # Windows 7
            default_entry = r'Microsoft\Windows\Themes\TranscodedWallpaper.jpg'
        elif win[1] == 2:  # Windows 8
            default_entry = r'Microsoft\Windows\Themes\TranscodedWallpaper'
    try:
        # Try the defualt location if available.
        if default_entry and ('APPDATA' in os.environ):
            wallpaper_path = os.path.join(os.environ['APPDATA'], default_entry)
            LOGGER.debug('Accessing: ' + wallpaper_path)
        # Get current current_wallpaper from registry if needed.
        if wallpaper_path and os.path.exists(wallpaper_path):
            wallpaper = wallpaper_path
        # We might have the default wallpaper now, but let's try
        # replace it with the current one...
        if reg_location:
            LOGGER.debug('reg_location: ' + str(reg_location))
            key = OpenKey(HKEY_CURRENT_USER, reg_location)
            LOGGER.debug('key: ' + str(key) + ' open!')
            wallpaper_path = QueryValueEx(key, 'Wallpaper')[0]
            LOGGER.debug('keyval: ' + str(wallpaper_path))
            if wallpaper_path.count('%') > 1:
                index_start = wallpaper_path.find('%')
                index_end = wallpaper_path.find('%', index_start + 1)
                env = wallpaper_path[index_start + 1:index_end]
                end = wallpaper_path[index_end + 2:]
                wallpaper_path = os.path.join(os.getenv(env), end)
            LOGGER.debug('keyval2: ' + str(wallpaper_path))
            if (wallpaper_path) and len(wallpaper_path):
                wallpaper = wallpaper_path
    except (ValueError, IOError, OSError) as excp:
        LOGGER.exception('get_current_wallpaper exception: {0!s}'.format(excp))
    if key is not None:
        CloseKey(key)
    return wallpaper


def get_file_extension(path):
    """
    Returns the file extension of a file

    :param path: The file path.
    :type path: String

    :rtype: String

    """
    result = ''
    try:
        (file_name, file_extension) = os.path.splitext(path)
        if file_name:
            # for example .config actually is not a extension but filename.
            # That's why we filter out "extensions" of "nameless" files.
            result = file_extension
    except (ValueError, IOError, OSError):
        pass
    return result


def get_node_image(node):
    """
    Searches for a node's image in STORAGE.

    :param node: The node id.
    :type node: Integer

    """
    result = ''
    try:
        result = os.path.join(os.getcwd(), diwavars.DEFAULT_SCREEN)
    except (ValueError, IOError, OSError):
        pass
    try:
        node = str(node)
        img_path = os.path.join(r'\\' + diwavars.STORAGE, 'screen_images',
                                str(node) + '.png')
        if os.path.exists(img_path):
            result = img_path
    except (ValueError, IOError, OSError):
        pass
    return result


def open_file(filepath):
    """
    Opens a file path.

    :param filepath: The file path.
    :type filepath: String

    """
    LOGGER.debug(u'{0} opening file {1}'.format(os.name, filepath))
    try:
        if os.path.exists(filepath):
            try:
                os.startfile(filepath)
            except OSError:
                subprocess.call((u'start', filepath), shell=True)
    except OSError as excp:
        # Subprocess.call failed!
        LOGGER.exception(u'Open file exception: {0!s}'.format(excp))


def save_screen(filepath):
    """
    Saves the background image of the desktop.

    :param filepath: The filepath for the saved image.
    :type filepath: String

    """
    def calculate_framebox(frame_image):
        """
        Inner function for calculating the frame box of non-alpha area.

        """
        left_upper = (0, 0)
        right_lower = (0, 0)
        (red, green, blue, alpha) = frame_image.split()
        if not alpha:
            return (left_upper, right_lower)
        # getbbox finds the first non-zero pixel so we need inverse of alpha.
        alpha = ImageOps.invert(alpha)
        mybox = alpha.getbbox()
        if mybox:
            left_upper = (mybox[0], mybox[1])
            right_lower = (mybox[2] - mybox[0], mybox[3] - mybox[1])
        return (left_upper, right_lower)

    LOGGER.debug('save_screen("' + filepath + '")')
    win = (diwavars.WINDOWS_MAJOR, diwavars.WINDOWS_MINOR)
    current_wallpaper = get_current_wallpaper(win)
    if current_wallpaper is None:
        return
    try:
        background = Image.open(current_wallpaper)
        # mask, that we overlay
        frame_mask = Image.open(os.path.join('data', 'scr_frame_mask.png'))
        frame_mask = frame_mask.convert('RGBA')
        # Calculate the area with alpha.
        (img_pos, img_size) = calculate_framebox(frame_mask)
        # Resize the wallpaper to the alpha area.
        cropped_image = ImageOps.fit(background, img_size,
                                     method=Image.ANTIALIAS)
        # Paste over the alpha area and save the image.
        frame_mask.paste(cropped_image, box=img_pos)
        frame_mask.save(filepath, format='PNG')
    except (IOError, OSError) as excp:
        LOGGER.exception('save_screen Exception: {0!s}'.format(excp))


def screen_capture(path, node_id):
    """
    Take a screenshot and store it in project folder.

    :param path: Path to the project folder.
    :type path: String

    :param node_id: NodeID
    :type node_id: Integer

    """
    try:
        grab = ImageGrab.grab()
        grab.thumbnail((800, 600), Image.ANTIALIAS)
        filepath = os.path.join(path, 'Screenshots')
        try:
            os.makedirs(filepath)
        except OSError:
            pass
        event_id = controller.get_latest_event_id()
        stringform = datetime.datetime.now().strftime('%d%m%Y%H%M%S')
        nameform = '{0}_{1}_{2}.png'.format(event_id, node_id, stringform)
        filepath = os.path.join(filepath, nameform)
        grab.save(filepath, format='PNG')
    except (IOError, OSError) as excp:
        LOGGER.exception('screen_capture exception: {0!s}'.format(excp))


def search_file(filename, search_path, case_sensitive=True):
    """
    Search file in a given path.

    :param filename: The file name.
    :type filename: String

    :param search_path: The search path.
    :type search_path: String

    :returns: The path to the file.
    :rtype: String

    """
    if not filename or not search_path or not os.path.exists(search_path):
        return ''
    if not case_sensitive:
        filename = filename.lower()
    for (root, directories, files) in os.walk(search_path):
        if not case_sensitive:
            files = [fname.lower() for fname in files]
        if filename in files:
            return os.path.join(root, filename)
    return ''


def test_storage_connection():
    """
    Try to access \\\\Storage\\Projects

    :returns: Does the path exist.
    :rtype: Boolean

    """
    try:
        return os.path.exists(r'\\{0}\Projects'.format(diwavars.STORAGE))
    except (IOError, OSError):
        return False
