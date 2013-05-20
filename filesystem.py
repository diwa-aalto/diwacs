'''
Created on 17.5.2013

'''
# System imports.
import base64
import datetime
import os
import shutil
import subprocess
import tempfile
import threading
import urllib2
from _winreg import (OpenKey, CloseKey, HKEY_CURRENT_USER, QueryValueEx)
import xmlrpclib

# 3rd party imports.
from PIL import Image, ImageOps, ImageGrab


# Own imports.
import controller
import utils
import diwavars
STORAGE = diwavars.STORAGE
CAMERA_URL = diwavars.CAMERA_URL
CAMERA_USER = diwavars.CAMERA_USER
CAMERA_PASS = diwavars.CAMERA_PASS


def CopyFileToProject(filepath, project_id):
    """ Copy file to project dir and return new filepath in project dir.

    :param filepath: The file path.
    :type filepath: String.
    :param project_id: Project id from database.
    :type project_id: Integer.

    """
    s = SearchFile(os.path.basename(filepath),
                   controller.GetProjectPath(project_id))
    if not s:
        try:
            project_dir = controller.GetProjectPath(project_id)
            shutil.copy2(filepath, project_dir)
        except:
            utils.logger.exception('File copy error')
            return False
        return os.path.join(project_dir,
                            os.path.basename(filepath))
    else:
        return s


def CopyToTemp(filepath):
    """Copy a file to temporary folder.

    :param filepath: The file path.
    :type filepath: String.

    """
    try:
        temp_path = os.path.join(controller.PROJECT_PATH, 'temp')
        if not os.path.exists(temp_path):
            os.makedirs(temp_path)
        extension = GetFileExtension(filepath)
        (fd, temp) = tempfile.mkstemp(dir=temp_path, suffix=extension)
        os.close(fd)
        shutil.copy(filepath, temp)
        return temp
    except:
        return False


def CreateProjectDir(dir_name):
    """Creates a project directory, if one does not exist in the file system

    :param dir_name: Name of the directory
    :type dir_name: String.

    """
    project_dir = os.path.join(controller.PROJECT_PATH, str(dir_name))
    if not os.path.exists(project_dir):
        try:
            os.makedirs(project_dir)
        except:
            utils.logger.exception("Error creating project dir.")
            return None
        return project_dir
    return None


def DeleteDir(path):
    result = False
    try:
        shutil.rmtree(path)
        result = True
    except:
        utils.logger.exception("Delete dir exception")
    return result


def FileToBase64(filepath):
    """Transform a file to a binary object.

    :param filepath: The file path.
    :type filepath: String.

    """
    try:
        bin_obj = xmlrpclib.Binary(open(filepath, "rb").read())
        return bin_obj
    except:
        return False


# Module global constants.
__WIN_XP_REG = r'Software\Microsoft\Windows\CurrentVersion\Themes\LastTheme'
__WIN_VISTA7_REG = r'Control Panel\Desktope'


def GetCurrentWallpaper(win):
    wallpaper = None
    key = None
    default_entry = None
    reg_location = None
    if win == 5:
        reg_location = __WIN_XP_REG
    elif win in [6, 7]:
        reg_location = __WIN_VISTA7_REG
        default_entry = 'Microsoft\Windows\Themes\TranscodedWallpaper'
        if win == 6:
            default_entry += '.jpg'
    try:
        # Try the defualt location if available.
        if default_entry and ('APPDATA' in os.environ):
            wallpaper_path = os.path.join(os.environ['APPDATA'], default_entry)
        # Get current current_wallpaper from registry if needed.
        if wallpaper_path and os.path.exists(wallpaper_path):
            wallpaper = wallpaper_path
        elif reg_location:
            key = OpenKey(HKEY_CURRENT_USER, reg_location)
            wallpaper_path = QueryValueEx(key, 'Wallpaper')[0]
            if wallpaper_path.count("%") > 1:
                i1 = wallpaper_path.find("%")
                i2 = wallpaper_path.find("%", i1 + 1)
                env = wallpaper_path[i1 + 1:i2]
                end = wallpaper_path[i2 + 2:]
                wallpaper_path = os.path.join(os.getenv(env), end)
            wallpaper = wallpaper_path
    except:
        wallpaper = None
    if key is not None:
        CloseKey(key)
    return wallpaper


def GetFileExtension(path):
    """Returns the file extension of a file

    :param path: The file path.
    :type path: String
    :rtype: String.

    """
    (unused_fileName, fileExtension) = os.path.splitext(path)
    return fileExtension


def GetNodeImg(node):
    """Searches for a node's image in STORAGE.

    :param node: The node id.
    :type node: Integer.

    """
    node = str(node)
    img_path = '\\\\' + STORAGE + '\\screen_images\\' + str(node) + '.png'
    if os.path.exists(img_path):
        return img_path
    return os.path.join(os.getcwd(), diwavars.DEFAULT_SCREEN)


def IsSubtree(filename, parent):
    """Determines, if filename is inside the parent folder.

    :param filename: The file path.
    :type filename: String.
    :param parent: The parent file path.
    :type parent: String.

    """
    for (unused_root, unused_dirs, names) in os.walk(parent):
        if filename in names:
            return True
    return False


""" List operations: difference and intersection  """
diff = lambda l1, l2: [x for x in l1 if x not in l2]
intr = lambda l1, l2: [x for x in l1 if x in l2]


def OpenedFilesQuery():
    """Calls the openedfilesview. """
    subprocess.call('ofv//OpenedFilesView.exe /scomma ofv.csv')


def OpenFile(filepath):
        """Opens a file path.

        :param filepath: The file path.
        :type filepath: String.

        """
        utils.logger.debug("%s Opening file %s", (os.name, filepath))
        if os.name == 'mac':
            subprocess.call(('open', filepath))
        elif os.name == 'nt':
            try:
                if os.path.exists(filepath):
                    try:
                        os.startfile(filepath)
                    except:
                        subprocess.call(('start', filepath), shell=True)
            except:
                utils.logger.exception("Open file exception")
        elif os.name == 'posix':
            subprocess.call(('xdg-open', filepath))


def RecentFilesQuery():
    """Calls the recentfilesview. """
    subprocess.call('rfv//RecentFilesView.exe /scomma rfv.csv /sort ~3')


def SaveScreen(win, filepath):
    """Saves the background image of the desktop.

    :param filename: The filename for the saved image.
    :type filename: String.

    """
    current_wallpaper = GetCurrentWallpaper(win)
    if current_wallpaper is None:
        return
    try:
        #From blog :
        #http://tobias.klpstn.com/2008/02/10/simple-image-masking-with-pil/
        # the image we want to paste in the transparent mask
        background = Image.open(current_wallpaper)
        # or take screenshot
        #: TODO: Consider refactoring out.
        unused_grab = ImageGrab.grab()
        # the mask, where we insert our image
        mask = Image.open(os.path.join("data", "scr_mask.png"))
        # mask, that we overlay
        frame_mask = Image.open(os.path.join("data", "scr_frame_mask.png"))
        # smooth the mask a little bit, if you want
        # mask = mask.filter(ImageFilter.SMOOTH)
        # resize/crop the image to the size of the mask-image
        cropped_image = ImageOps.fit(background, mask.size,
                                     method=Image.ANTIALIAS)
        # get the alpha-channel (used for non-replacement)
        cropped_image = cropped_image.convert("RGBA")
        mask.load()
        (unused_r, unused_g, unused_b, a) = mask.split()
        # paste the frame mask without replacing the alpha mask of the
        # mask-image.
        cropped_image.paste(frame_mask, mask=a)
        cropped_image.save(filepath, format="PNG")
    except Exception as inst:
        utils.logger.exception('SaveScreen Exception: %s', str(inst))


def ScreenCapture(path, node):
    try:
        grab = ImageGrab.grab()
        grab.thumbnail((800, 600), Image.ANTIALIAS)
        filepath = os.path.join(path, "Screenshots")
        try:
            os.makedirs(filepath)
        except:
            pass
        event_id = controller.GetLatestEvent()
        stringform = datetime.datetime.now().strftime("%d%m%Y%H%M%S")
        filepath = os.path.join(filepath, str(event_id) + '_' + node + '_' +
                                stringform + '.png')
        grab.save(filepath, format='PNG')
    except Exception, e:
        utils.logger.exception('ScreenCapture exception:%s', str(e))


def SearchFile(filename, search_path):
    """Search file in a given path.

    :param filename: The file name.
    :type filename: String.
    :param search_path: The search path.
    :type search_path: String.

    """
    #: TODO: Implementation is invalid.
    if not search_path or not os.path.exists(search_path):
        return None
    file_found = 0
    paths = search_path.split(os.path.pathsep)
    for path in paths:
        if os.path.exists(os.path.join(path, filename)):
            file_found = 1
            break
    if file_found:
        return os.path.abspath(os.path.join(path, filename))
    else:
        return None


def Snaphot(path):
    thread = threading.Thread(target=SnaphotThread, args=(path,))
    thread.daemon = True
    thread.start()


def SnaphotThread(path):
    filepath = os.path.join(path, "Snapshots")
    try:
        os.makedirs(filepath)
    except:
        pass
    request = urllib2.Request(diwavars.CAMERA_URL)
    base64string = base64.encodestring('%s:%s' % (diwavars.CAMERA_USER,
                                                  diwavars.CAMERA_PASS))
    base64string = base64string.replace('\n', '')
    request.add_header("Authorization", "Basic %s" % base64string)
    event_id = controller.GetLatestEvent()
    try:
        data = urllib2.urlopen(request, timeout=60).read()
        name = str(event_id) + '_' + (
                    datetime.datetime.now().strftime("%d%m%Y%H%M%S") + '.jpg')
        utils.logger.debug('Snaphot filename: %s', name)
        output = open(os.path.join(filepath, name), 'wb')
        output.write(data)
        output.close()
    except Exception, e:
        utils.logger.exception("Snapshot exception: %s", str(e))


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


def UpdateStorage(storage):
    global STORAGE
    STORAGE = storage