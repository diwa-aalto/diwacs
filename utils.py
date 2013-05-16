'''
Created on 9.5.2012

@author: neriksso

@requires: WMI

@requires: wxPython
'''

# Standard library imports go here.
import base64
import datetime
import hashlib
import logging.config
import os
from os.path import exists, join, abspath
import shutil
import socket
import subprocess
import tempfile
import threading
import urllib2
import zipfile
from _winreg import (HKEY_CLASSES_ROOT, KEY_ALL_ACCESS, OpenKey, CloseKey,
                    EnumKey, DeleteKey, CreateKey, SetValueEx, REG_SZ,
                    HKEY_CURRENT_USER, QueryValueEx)
import xmlrpclib

# Third party library imports go here.
from PIL import Image, ImageOps, ImageFilter,ImageGrab,PngImagePlugin
import win32wnet
from win32netcon import RESOURCETYPE_DISK as DISK
import wmi
import wx

# Imports from DiWaCS go here.
import controller
from vars import CAMERA_URL, CAMERA_USER, CAMERA_PASS

# Some module variables.
STORAGE = "192.168.1.10"
logging.config.fileConfig(os.path.abspath('logging.conf'))
logger = logging.getLogger('utils')
SENDKEYS_TABLE_VIRTUAL = (
    (0x08,"{BACKSPACE}"),
    (0x09,"{TAB}"),     
    (0x0D,"{ENTER}"),  
    (0x1B,"{ESC}"),   
    (0x20,"{SPACE}"),    
    (0x2E,"{DEL}"), 
    (19,"{BREAK}"), 
    (0x14,"{CAP}"), 
    (0x23,"{END}"), 
    (0x24,"{HOME}"), 
    (0x25,"{LEFT}"), 
    (0x26,"{UP}"), 
    (0x27,"{RIGHT}"), 
    (0x28,"{DOWN}"), 
    (0x29,""), 
    (0x2A,"{PRTSC}"),  
    (44,""), 
    (0x2C,"{INSERT}"), 
    (0x2F,"{HELP}"), 
    (0x60,"0"), 
    (0x61,"1"), 
    (0x62,"2"), 
    (0x63,"3"), 
    (0x64,"4"), 
    (0x65,"5"), 
    (0x66,"6"), 
    (0x67,"7"), 
    (0x68,"8"), 
    (0x69,"9"), 
    (0x6A,"{MULTIPLY}"), 
    (0x6B,"{ADD}"), 
    (0x6C,""), 
    (0x6D,"{SUBTRACT}"), 
    (0x6E,""), 
    (0x6F,"{DIVIDE}"), 
    (112,"{F1}"), 
    (113,"{F2}"), 
    (114,"{F3}"), 
    (115,"{F4}"), 
    (115,"{F5}"), 
    (116,"{F6}"), 
    (117,"{F7}"), 
    (118,"{F8}"), 
    (119,"{F9}"), 
    (120,"{F10}"), 
    (121,"{F11}"), 
    (122,"{F12}"),
    (123,"{F13}"), 
    (124,"{F14}"), 
    (125,"{F15}"), 
    (126,"{F16}"), 
    (127,"{F17}"), 
    (128,"{F18}"), 
    (129,"{F19}"), 
    (130,"{F20}"), 
    (131,"{F21}"), 
    (132,"{F22}"), 
    (133,"{F23}"), 
    (134,"{F24}"), 
    (0x90,"{NUMLOCK}"), 
    (145,"{SCROLLLOCK}"), 
    (0x21,"{PGUP}"), 
    (0x22,"{PGDN}"),
    (0xA4,"{LWIN}"), 
    (0x5C,"{RWIN}"), 
    (0x5B,"{LWIN}"), 
    (0x5C,"{RWIN}"), 
    ) 
SENDKEYS_TABLE = (
    (wx.WXK_BACK,"{BACKSPACE}"),
    (wx.WXK_TAB,"{TAB}"),     
    (wx.WXK_RETURN,"{ENTER}"),  
    (wx.WXK_ESCAPE,"{ESC}"),   
    (wx.WXK_SPACE,"{SPACE}"),    
    (wx.WXK_DELETE,"{DEL}"),   
    (wx.WXK_START,""),    
    (wx.WXK_LBUTTON,""), 
    (wx.WXK_RBUTTON,""), 
    (wx.WXK_CANCEL,""), 
    (wx.WXK_MBUTTON,""), 
    (wx.WXK_CLEAR,""), 
    (wx.WXK_SHIFT,""), 
    (wx.WXK_ALT,""), 
    (wx.WXK_CONTROL,""), 
    (wx.WXK_MENU,""), 
    (wx.WXK_PAUSE,"{BREAK}"), 
    (wx.WXK_CAPITAL,"{CAP}"), 
    (wx.WXK_END,"{END}"), 
    (wx.WXK_HOME,"{HOME}"), 
    (wx.WXK_LEFT,"{LEFT}"), 
    (wx.WXK_UP,"{UP}"), 
    (wx.WXK_RIGHT,"{RIGHT}"), 
    (wx.WXK_DOWN,"{DOWN}"), 
    (wx.WXK_SELECT,""), 
    (wx.WXK_PRINT,"{PRTSC}"), 
    (wx.WXK_EXECUTE,""), 
    (wx.WXK_SNAPSHOT,""), 
    (wx.WXK_INSERT,"{INSERT}"), 
    (wx.WXK_HELP,"{HELP}"), 
    (wx.WXK_NUMPAD0,"0"), 
    (wx.WXK_NUMPAD1,"1"), 
    (wx.WXK_NUMPAD2,"2"), 
    (wx.WXK_NUMPAD3,"3"), 
    (wx.WXK_NUMPAD4,"4"), 
    (wx.WXK_NUMPAD5,"5"), 
    (wx.WXK_NUMPAD6,"6"), 
    (wx.WXK_NUMPAD7,"7"), 
    (wx.WXK_NUMPAD8,"8"), 
    (wx.WXK_NUMPAD9,"9"), 
    (wx.WXK_MULTIPLY,"{MULTIPLY}"), 
    (wx.WXK_ADD,"{ADD}"), 
    (wx.WXK_SEPARATOR,""), 
    (wx.WXK_SUBTRACT,"{SUBTRACT}"), 
    (wx.WXK_DECIMAL,""), 
    (wx.WXK_DIVIDE,"{DIVIDE}"), 
    (wx.WXK_F1,"{F1}"), 
    (wx.WXK_F2,"{F2}"), 
    (wx.WXK_F3,"{F3}"), 
    (wx.WXK_F4,"{F4}"), 
    (wx.WXK_F5,"{F5}"), 
    (wx.WXK_F6,"{F6}"), 
    (wx.WXK_F7,"{F7}"), 
    (wx.WXK_F8,"{F8}"), 
    (wx.WXK_F9,"{F9}"), 
    (wx.WXK_F10,"{F10}"), 
    (wx.WXK_F11,"{F11}"), 
    (wx.WXK_F12,"{F12}"), 
    (wx.WXK_F13,"{F13}"), 
    (wx.WXK_F14,"{F14}"), 
    (wx.WXK_F15,"{F15}"),
    (wx.WXK_F16,"{F16}"), 
    (wx.WXK_F17,"{F17}"), 
    (wx.WXK_F18,"{F18}"), 
    (wx.WXK_F19,"{F19}"), 
    (wx.WXK_F20,"{F20}"), 
    (wx.WXK_F21,"{F21}"), 
    (wx.WXK_F22,"{F22}"), 
    (wx.WXK_F23,"{F23}"), 
    (wx.WXK_F24,"{F24}"), 
    (wx.WXK_NUMLOCK,"{NUMLOCK}"), 
    (wx.WXK_SCROLL,"{SCROLLLOCK}"), 
    (wx.WXK_PAGEUP,"{PGUP}"), 
    (wx.WXK_PAGEDOWN,"{PGDN}"), 
    (wx.WXK_NUMPAD_SPACE,"{SPACE}"), 
    (wx.WXK_NUMPAD_TAB,"{TAB}"), 
    (wx.WXK_NUMPAD_ENTER,"{ENTER}"), 
    (wx.WXK_NUMPAD_F1,"{F1}"), 
    (wx.WXK_NUMPAD_F2,"{F2}"), 
    (wx.WXK_NUMPAD_F3,"{F3}"), 
    (wx.WXK_NUMPAD_F4,"{F4}"), 
    (wx.WXK_NUMPAD_HOME,"{HOME}"), 
    (wx.WXK_NUMPAD_LEFT,"{LEFT}"), 
    (wx.WXK_NUMPAD_UP,"{UP}"), 
    (wx.WXK_NUMPAD_RIGHT,"{RIGHT}"), 
    (wx.WXK_NUMPAD_DOWN,"{DOWN}"), 
    (wx.WXK_NUMPAD_PAGEUP,"{PGUP}"), 
    (wx.WXK_NUMPAD_PAGEDOWN,"{PGDN}"), 
    (wx.WXK_NUMPAD_END,"{END}"), 
    (wx.WXK_NUMPAD_BEGIN,""), 
    (wx.WXK_NUMPAD_INSERT,"{INSERT}"), 
    (wx.WXK_NUMPAD_DELETE,""), 
    (wx.WXK_NUMPAD_EQUAL,""), 
    (wx.WXK_NUMPAD_MULTIPLY,"{MULTIPLY}"), 
    (wx.WXK_NUMPAD_ADD,"{ADD}"), 
    (wx.WXK_NUMPAD_SEPARATOR,""), 
    (wx.WXK_NUMPAD_SUBTRACT,"{SUBTRACT}"), 
    (wx.WXK_NUMPAD_DECIMAL,""), 
    (wx.WXK_NUMPAD_DIVIDE,"{DIVIDE}"), 
    (wx.WXK_WINDOWS_LEFT,"{LWIN}"), 
    (wx.WXK_WINDOWS_RIGHT,"{RWIN}"), 
    (wx.WXK_WINDOWS_MENU,"{LWIN}"), 
    (wx.WXK_COMMAND,""),
    )

def get_local_ip_address(target):
    ipaddr = ''
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((target, 8000))
        ipaddr = s.getsockname()[0]
        s.close()
    except:
        ipaddr = None
    return ipaddr 

def get_lan_machines(lan_ip):
    index = lan_ip.rfind('.')
    if index > -1:
        lan_space = lan_ip[0:index]
    else:
        #print "given ip is not valid"
        return []
    arp_table = subprocess.Popen('arp -a',shell=True,stdout=subprocess.PIPE)
    list = []
    for line in arp_table.stdout:
        if line.find(lan_ip) > -1:
            primary = True
            continue
        if not line.strip():
            primary = False
        if primary and line.count('.') == 3 and line.split()[0].find(lan_space) > -1:
            list.append(line.split()[0])
    return list        


def SetLoggerLevel(level):
    logger.setLevel(level)
    
def UpdateStorage(storage):
    global STORAGE
    STORAGE = storage
    
def UpdateCameraVars(url,user,passwd):
    global CAMERA_URL, CAMERA_USER, CAMERA_PASS
    if url:
        CAMERA_URL = url
    if user:
        CAMERA_USER = user
    if passwd:
        CAMERA_PASS = passwd
            
def GetSendkeys(code):
    """Returns a character for a key code.
    
    :param code: The character code.
    :type code: Integer."""
    if code >=65 and code <=122:
        return chr(code)
    else:
        return next( (v for i,(k,v) in enumerate(SENDKEYS_TABLE_VIRTUAL) if k==code),None)
  
def OpenFile(filepath):
        """Opens a file path.
        
        :param filepath: The file path.
        :type filepath: String.
        
        """
        logger.debug("%s Opening file %s",(os.name,filepath))
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
                logger.exception("Open file exception")
                    
        elif os.name == 'posix':
            subprocess.call(('xdg-open', filepath)) 
            
def Snaphot(path):
    thread = threading.Thread(target=SnaphotThread,args=(path,))
    thread.daemon=True
    thread.start()
            
def SnaphotThread(path):
    filepath = os.path.join(path,"Snapshots")
    try:
        os.makedirs(filepath)
    except:
        pass
    request = urllib2.Request(CAMERA_URL)
    base64string = base64.encodestring('%s:%s' % (CAMERA_USER, CAMERA_PASS)).replace('\n', '')
    request.add_header("Authorization", "Basic %s" % base64string)
    event_id = controller.GetLatestEvent()   
    try:
        data = urllib2.urlopen(request,timeout=60).read()
        name = str(event_id)+'_'+datetime.datetime.now().strftime("%d%m%Y%H%M%S")+'.jpg'
        logger.debug('Snaphot filename:%s',name)
        output = open(os.path.join(filepath,name),'wb')
        output.write(data)
        output.close()
    except Exception,e:
        logger.exception("Snapshot exception:%s",str(e))
                
def GetMacForIp(ip):
    """Returns the mac address for an local IP address.
    
    :param ip: IP address
    :type ip: String.
    
    """
    try:
        c = wmi.WMI()
        
        for interface in c.Win32_NetworkAdapterConfiguration(IPEnabled=1):
            print interface.Description, interface.MACAddress       
            for ip_address in interface.IPAddress:
                if ip_address == ip:
                    return str(interface.MACAddress).translate(None,':')
    except Exception,e:
        logger.debug("here")
        logger.exception("Exception in GetMacForIp")  
    return None

def DeleteDir(path):
    try:
        shutil.rmtree(path)
        return True
    except:
        logger.exception("Delete dir exception")
        return False       

def SaveScreen(win,filepath):

        """Saves the background image of the desktop.
        
        :param filename: The filename for the saved image.
        :type filename: String.
        
        """
        try:
            # Get current wallpaper from registry
            if win == 5:
                key = OpenKey(HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Themes\LastTheme')
                wallpaper_path = QueryValueEx(key,'Wallpaper')[0]
                logger.debug("XP wallpaper_path:%s"%wallpaper_path)
                if wallpaper_path.count("%"):
                    i1 = wallpaper_path.find("%")
                    i2 = wallpaper_path.find("%",i1+1)
                    env = wallpaper_path[i1+1:i2]
                    logger.debug("env:%s variable: %s"%(env,os.getenv(env)))
                    wallpaper = os.path.join(os.getenv(env),wallpaper_path[i2+2:])
                else:
                    wallpaper=wallpaper_path
            if win == 6:
                wallpaper = os.path.join(os.environ['APPDATA'],'Microsoft\Windows\Themes\TranscodedWallpaper.jpg')
                if not os.path.exists(wallpaper):
                    key = OpenKey(HKEY_CURRENT_USER,r'Control Panel\Desktope')
                    wallpaper_path = QueryValueEx(key,'Wallpaper')[0]
                    if wallpaper_path.count("%"):
                        i1 = wallpaper_path.find("%")
                        i2 = wallpaper_path.find("%",i1+1)
                        env = wallpaper_path[i1+1:i1]
                        wallpaper = os.path.join(os.getenv(env),wallpaper_path[i2+2:])
                    else:
                        wallpaper=wallpaper_path
                    
            if win == 7:
                wallpaper = os.path.join(os.environ['APPDATA'],'Microsoft\Windows\Themes\TranscodedWallpaper')
                if not os.path.exists(wallpaper):
                    key = OpenKey(HKEY_CURRENT_USER,r'Control Panel\Desktope')
                    wallpaper_path = QueryValueEx(key,'Wallpaper')[0]
                    if wallpaper_path.count("%"):
                        i1 = wallpaper_path.find("%")
                        i2 = wallpaper_path.find("%",i1+1)
                        env = wallpaper_path[i1+1:i1]
                        wallpaper = os.path.join(os.getenv(env),wallpaper_path[i2+2:])
                    else:
                        wallpaper=wallpaper_path
            #From blog : http://tobias.klpstn.com/2008/02/10/simple-image-masking-with-pil/
            # the image we want to paste in the transparent mask
            background = Image.open(wallpaper)
            # or take screenshot
            grab = ImageGrab.grab()       
            # the mask, where we insert our image
            mask = Image.open("scr_mask.png")
            # mask, that we overlay
            frame_mask = Image.open("scr_frame_mask.png")
            # smooth the mask a little bit, if you want
            # mask = mask.filter(ImageFilter.SMOOTH)
            # resize/crop the image to the size of the mask-image
            cropped_image = ImageOps.fit(background, mask.size, method=Image.ANTIALIAS)
            # get the alpha-channel (used for non-replacement)
            cropped_image = cropped_image.convert("RGBA")
            mask.load()
            r,g,b,a = mask.split()
            # paste the frame mask without replacing the alpha mask of the mask-image
            cropped_image.paste(frame_mask, mask=a)
            cropped_image.save(filepath,format="PNG")
        except Exception as inst:
            logger.exception('SaveScreen Exception')
                 
def ScreenCapture(path,node):
    try: 
        grab = ImageGrab.grab()
        grab.thumbnail((800,600), Image.ANTIALIAS)
        filepath = os.path.join(path,"Screenshots")
        try:
            os.makedirs(filepath)
        except:
            pass
        event_id = controller.GetLatestEvent()
        filepath = os.path.join(filepath,str(event_id)+'_'+node+'_'+datetime.datetime.now().strftime("%d%m%Y%H%M%S")+'.png')    
        grab.save(filepath,format='PNG')
    except Exception,e:
        logger.exception('ScreenCapture exception:%s',str(e))                            

def IntToDottedIP( intip ):
    """Transforms an Integer IP address to dotted representation.
    
    :param intip: The IP
    :type intip: Integer.
    
    """
    octet = ''
    for exp in [3,2,1,0]:
        octet = octet + str(intip / ( 256 ** exp )) + "."
        intip = intip % ( 256 ** exp )
    return(octet.rstrip('.'))
     
def DottedIPToInt( dotted_ip ):
    """Transforms a dotted IP address to Integer.
    
    :param dotted_ip: The IP address.
    :type dotted_ip: String.
    
    """
    print "dotted ip to int"
    st=dotted_ip.split('.') 
    return int("%02x%02x%02x%02x" % (int(st[0]),int(st[1]),int(st[2]),int(st[3])),16) 
               
def GetNodeImg(node):
    """Searches for a node's image in STORAGE.
    
    :param node: The node id.
    :type node: Integer.
    
    """
    node = str(node)
    img_path = '\\\\'+STORAGE+'\\screen_images\\'+str(node)+'.png'
    if os.path.exists(img_path):
        return img_path
    return 'SCREEN.png'

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
    
def CopyToTemp(filepath):
    """Copy a file to temporary folder.
    
    :param filepath: The file path.
    :type filepath: String.
    
    """
    try:
        temp_path = os.path.join(controller.PROJECT_PATH,'temp')
        if not os.path.exists(temp_path):
            os.makedirs(temp_path)
        fd,temp = tempfile.mkstemp(dir=temp_path,suffix=GetFileExtension(filepath))    
        os.close(fd)
        shutil.copy(filepath,temp) 
        return temp
    except:
        return False
    
def SearchFile(filename, search_path):
    """Search file in a given path.
    
    :param filename: The file name.
    :type filename: String.
    :param search_path: The search path.
    :type search_path: String.
    
    """
    if not search_path or not os.path.exists(search_path):
        return None
    file_found = 0
    paths = search_path.split(os.path.pathsep)
    for path in paths:
        if exists(join(path, filename)):
            file_found = 1
            break
    if file_found:
        return abspath(join(path, filename))
    else:
        return None

def IterIsLast(iterable):
    """ IterIsLast(iterable) -> generates (item, islast) pairs

    Generates pairs where the first element is an item from the iterable
    source and the second element is a boolean flag indicating if it is the
    last item in the sequence.

    :param iterable: The iterable element.
    :type iterable: iterable
    """

    it = iter(iterable)
    prev = it.next()
    for item in it:
        yield prev, False
        prev = item
    yield prev, True
                 
def CopyFileToProject(filepath,project_id):
    """ Copy file to project dir and return new filepath in project dir 
    
    :param filepath: The file path.
    :type filepath: String.
    :param project_id: Project id from database.
    :type project_id: Integer.
    
    """
    s = SearchFile(os.path.basename(filepath),controller.GetProjectPath(project_id))
    if not s:
        try:
            project_dir = controller.GetProjectPath(project_id)
            shutil.copy2(filepath,project_dir)
        except:
            logger.exception('File copy error')
            return False    
        return os.path.join(project_dir,os.path.basename(filepath))
    else:
        return s

def IsSubtree(filename,parent):
    """Determines, if filename is inside the parent folder.
    
    :param filename: The file path.
    :type filename: String.
    :param parent: The parent file path.
    :type parent: String.
    
    """
    for root, dirs, names in os.walk(parent):
        if filename in names:
            return True
    return False

""" List operations: difference and intersection  """    
diff = lambda l1,l2: [x for x in l1 if x not in l2]
intr = lambda l1,l2: [x for x in l1 if x in l2]

def RecentFilesQuery():
    """Calls the recentfilesview. """
    subprocess.call('rfv//RecentFilesView.exe /scomma rfv.csv /sort ~3')
    
def OpenedFilesQuery():
    """Calls the openedfilesview. """
    subprocess.call('ofv//OpenedFilesView.exe /scomma ofv.csv')    
        
def MapNetworkShare(letter,share):
    """Maps the network share to a letter 
    
    :param letter: The letter for which to map.
    :type letter: String.
    :param share: The network share.
    :type share: String.
    
    """
    try:
        win32wnet.WNetCancelConnection2(letter,1,1)
    except Exception,e:
        logger.exception("error mapping share %s %s %s",letter,share,str(e))
    
    try:        
        win32wnet.WNetAddConnection2(DISK, letter, share)
    except Exception,e:
        logger.exception("error mapping share %s %s %s",letter,share,str(e))

def GetProjectPassword(project_id):
    project = controller.GetProject(project_id)
    m = hashlib.sha1()
    m.update(str(project.id)+project.password if project.password else '')
    return m.hexdigest()
 
def HashPassword(password):
    m = hashlib.sha1()
    m.update(password)
    return m.hexdigest() 

def ArchiveProjectDir(project_id):
    path = controller.GetProjectPath(project_id)
    #print "archiving project",project_id
    zip_path = path+'.zip'
    if os.path.exists(zip_path):
        os.remove(zip_path)    
    password = GetProjectPassword(project_id)    
    subprocess.call(['7Zip64/7z', 'a', '-p'+password, '-y', zip_path] + [path])
    for the_file in os.listdir(path):
        file_path = os.path.join(path, the_file)
        try:
            os.unlink(file_path)
        except Exception, e:
            logger.exception('Archive project exception')
            
def ReturnProjectDir(project_id):
    path = controller.GetProjectPath(project_id)
    zip_path = path+'.zip'
    #print "get password hash"
    password = GetProjectPassword(project_id)
    #print "create zip"
    zipfile.ZipFile(zip_path).extractall(path=os.path.join(path,'../'),pwd=password)
    if os.path.exists(path):
        try:
            os.unlink(zip_path)
        except Exception, e:
            logger.exception('Unzip project dir exception')
                 
def CreateProjectDir(dir_name):
    """Creates a project directory, if one does not exist in the file system
    
    :param dir_name: Name of the directory
    :type dir_name: String.
    
    """
    project_dir = os.path.join(controller.PROJECT_PATH,str(dir_name))
    if not os.path.exists(project_dir):
        try:
            os.makedirs(project_dir)
        except:
            logger.exception("Error creating project dir.")
            return None                
        return project_dir
    return None        

def GetFileExtension(path):
    """Returns the file extension of a file
    
    :param path: The file path.
    :type path: String
    :rtype: String.
    
    """
    fileName, fileExtension = os.path.splitext(path)
    return fileExtension
