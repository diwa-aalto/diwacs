'''
Created on 8.5.2012

@author: neriksso
'''

#: TODO: Clean the imports...
from collections import deque
from datetime import datetime
import logging
import os
import Queue
from random import Random
#import re
import shutil
from subprocess import Popen
import sys
import threading
from time import sleep
import urllib2
import wave
import webbrowser
from _winreg import (KEY_ALL_ACCESS, OpenKey, CloseKey, EnumKey, DeleteKey,
                     CreateKey, SetValueEx, REG_SZ, HKEY_CURRENT_USER)
#from xmlrpclib import ExpatParser
sys.stdout = open("data\stdout.log", "wb")
sys.stderr = open("data\stderr.log", "wb")


# 3rd party imports.
import configobj
from lxml import etree
from pubsub import pub
import pyaudio
import pyHook
import pythoncom
from sqlalchemy import exc
from urlparse import urlparse
from watchdog.observers import Observer
import wx
import wx.lib.buttons as buttons
import zmq

try:
    from agw import ultimatelistctrl as ULC
#if it's not there locally, try the wxPython lib.
except ImportError:
    from wx.lib.agw import ultimatelistctrl as ULC

# Own imports.
import controller
import diwavars
import filesystem
import macro
from models import Company, Project
import swnp
import utils


logging.config.fileConfig('logging.conf')
wos_logger = logging.getLogger('wos')
CONTROLLED = False
CONTROLLING = False


def SetLoggerLevel(level):
    """ Used to set wos_logger level.
    :param level: The level desired.
    :type level: Integer

    """
    wos_logger.setLevel(level)


class AudioRecorder(threading.Thread):
    """A thread for capturing audio continuously.
    It keeps a buffer that can be saved to a file.
    By convention AudioRecorder is usually written in mixedcase although we
    prefer uppercase for threading types.

    :param parent: Parent of the thread.
    :type parent: :py:class:`threading.Thread`

    """
    def __init__(self, parent):
        threading.Thread.__init__(self, name="AudioRecorder")
        self.parent = parent
        self.pa = pyaudio.PyAudio()
        self.stream = self.open_mic_stream()
        self.buffer = deque(maxlen=diwavars.MAX_LENGTH)
        self.listening = True

    def stop(self):
        self.listening = False
        self.stream.close()

    def find_input_device(self):
        device_index = None
        for i in range(self.pa.get_device_count()):
            # China hack...
            """logger.debug("Selecting audio device %s / %s " %
            (str(i),str(self.pa.get_device_count())))
            device_index = i
            return device_index
            """
            devinfo = self.pa.get_device_info_by_index(i)
            for keyword in ["mic", "input"]:
                if keyword in devinfo["name"].lower():
                    device_index = i
                    return device_index

        if device_index == None:
            pass

        return device_index

    def open_mic_stream(self):
        device_index = None
        # uncomment the next line to search for a device.
        # device_index = self.find_input_device()
        stream = self.pa.open(
                        format=diwavars.FORMAT,
                        channels=diwavars.CHANNELS,
                        rate=diwavars.RATE,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=diwavars.INPUT_FRAMES_PER_BLOCK
                        )
        return stream

    def run(self):
        """Continuously record from the microphone to the buffer.
        If the buffer is full, the first frame will be removed and
        the new block appended.

        """
        while self.listening:
            try:
                data = self.stream.read(diwavars.INPUT_FRAMES_PER_BLOCK)
                if len(self.buffer) == self.buffer.maxlen:
                    d = self.buffer.popleft()
                    del d
                self.buffer.append(data)
            except IOError, e:
                wos_logger.exception("Error recording: %s" % (e))

    def save(self, ide, path):
        """Save the buffer to a file."""
        try:
            filename = (str(ide) + "_" +
                        datetime.now().strftime("%d%m%Y%H%M") + ".wav")
            filepath = os.path.join(path, 'Audio')
            if not os.path.exists(filepath):
                os.makedirs(filepath)
            filepath = os.path.join(filepath, filename)
            wf = wave.open(filepath, 'wb')
            wf.setnchannels(diwavars.CHANNELS)
            wf.setsampwidth(self.pa.get_sample_size(diwavars.FORMAT))
            wf.setframerate(diwavars.RATE)
            wf.writeframes(b''.join(self.buffer))
            wf.close()
            wx.CallAfter(self.parent.ClearStatusText)
        except:
            wos_logger.exception("audio save exception")
            wx.CallAfter(self.parent.ClearStatusText)


class UpdateDialog(wx.Dialog):
    """ A Dialog which notifies about a software update.
    Contains the URL which the user can click on.

    :param title: Title of the dialog.
    :type title: String
    :param url: URL of the update.
    :type url: String
    """
    def __init__(self, title, url, *args, **kwargs):
        super(UpdateDialog, self).__init__(parent=wx.GetApp().GetTopWindow(),
                                           title="Version %s is available" %
                                           title,
                                           style=wx.DEFAULT_DIALOG_STYLE |
                                           wx.STAY_ON_TOP,
                                           *args, **kwargs)
        self.notice = wx.StaticText(self, label="An application update is "\
                                    "available for %s at " %
                                    diwavars.APPLICATION_NAME)
        self.link = wx.HyperlinkCtrl(self, label="here.", url=url)
        self.link.Bind(wx.EVT_HYPERLINK, self.UrlHandler)
        self.ok = wx.Button(self, -1, "OK")
        self.ok.Bind(wx.EVT_BUTTON, self.OnOk)
        self.vsizer = wx.BoxSizer(wx.VERTICAL)
        self.hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.hsizer.Add(self.notice)
        self.hsizer.Add(self.link)
        self.vsizer.Add(self.hsizer)
        self.vsizer.Add(self.ok)
        self.SetSizer(self.vsizer)
        self.CenterOnScreen()
        self.vsizer.Fit(self)
        self.SetFocus()

    def OnOk(self, unused_event):
        self.EndModal(0)

    def UrlHandler(self, unused_event):
        webbrowser.open(self.link.GetURL())


class CHECK_UPDATE(threading.Thread):
    """Thread for checking version updates.
    """
    def __init__(self):
        threading.Thread.__init__(self, name="VersionChecker")

    def getPad(self):
        return urllib2.urlopen(diwavars.PAD_URL)

    def showDialog(self, url):
        try:
            dlg = UpdateDialog(self.latest_version, url).Show()
            dlg.Destroy()
        except:
            wos_logger.exception("Update Dialog Exception")

    def run(self):
        try:
            padfile = self.getPad()
            tree = etree.parse(padfile)
        except urllib2.URLError:
            wos_logger.exception("update checker exception retrieving padfile")
            return False
        except etree.XMLSyntaxError:
            wos_logger.exception("Update checker exception parsing padfile")
            return False
        except etree.ParseError:
            wos_logger.exception("Update checker exception parsing padfile")
            return False
        except Exception, e:
            wos_logger.exception("Update checker exception, generic: %s",
                                 str(e))
            return False
        latest_version = tree.findtext('Program_Info/Program_Version')
        url_primary = tree.findtext('Proram_Info/Web_Info/Application_URLs/'\
                                    'Primary_Download_URL')
        url_secondary = tree.findtext('Proram_Info/Web_Info/Application_URLs/'\
                                      'Secondary_Download_URL')
        url = url_primary if url_primary else url_secondary
        if latest_version > diwavars.VERSION:
            wx.CallAfter(self.showDialog, url)


class CONN_ERR_TH(threading.Thread):
    """Thread for checking connection errors.

    :param parent: Parent object.
    :type parent: wx.Frame.

    """
    def __init__(self, parent):
        threading.Thread.__init__(self, name="Connection Error Checker")
        self._stop = threading.Event()
        self.queue = Queue.Queue()
        self.parent = parent

    def run(self):
        """Starts the thread."""
        while not self._stop.isSet():
            if not self.queue.empty():
                try:
                    self.queue.get()
                    wx.CallAfter(pub.sendMessage, "ConnectionErrorHandler",
                                 error=True)
                except Exception:
                    wos_logger.exception('connection error checker exception')


class CloseError(Exception):
    """ Class describing an error while closing application.

    """
    def __init__(self, *args, **kwds):
        Exception.__init__(self, *args, **kwds)

    def __str__(self):
        return 'CloseError'


class BlackOverlay(wx.Frame):
    """
    Create a frame, size is full display size, wx.DisplaySize()
    gives width, height tuple of display screen.

    """
    def __init__(self, pos, size, parent):
        wx.Frame.__init__(self, parent, wx.ID_ANY, '', pos=pos, size=size,
                          style=0)  # style=wx.STAY_ON_TOP)
        self.panel = wx.Panel(self, -1, size=size)
        pos = [x / 2 for x in wx.DisplaySize()]
        labeltext = "Press alt + win to end remote control."
        self.exit_label = wx.StaticText(self.panel, -1, label=labeltext,
                                        style=wx.ALIGN_CENTER)
        font = wx.Font(18, wx.DECORATIVE, wx.ITALIC, wx.NORMAL)
        self.exit_label.SetFont(font)
        self.exit_label.SetForegroundColour('white')
        self.SetBackgroundColour('black')
        self.SetTransparent(200)
        self.parent = parent
        # set the cursor for the window
        self.SetCursor(BLANK_CURSOR)

    def ParseMouseEvents(self):
        mx = -1
        my = -1
        while True:
            if self.mouse_queue:
                event = self.mouse_queue.popleft()
                wos_logger.debug(event)
                if event[0] == 0x200:
                    dx = mx - event[1] if mx > 0 else event[1]
                    dy = my - event[2] if my > 0 else event[2]
                    mx = event[1]
                    my = event[2]

                    for id_ in self.parent.selected_nodes:
                        wos_logger.debug('mouse_move;%d,%d' % (int(dx),
                                                               int(dy)))
                        self.swnp(id_, 'mouse_move;%d,%d' % (int(dx), int(dy)))
                else:
                    for id_ in self.parent.selected_nodes:
                        wos_logger.debug('mouse_event;%d,%d' %
                                         (int(event.Message), int(event.Wheel))
                                         )
                        self.swnp(id_, 'mouse_event;%d,%d' %
                                  (int(event.Message), int(event.Wheel)))

    def DisableFocus(self, evt):
        evt.Skip()
        self.parent.panel.SetFocus()


class WORKER_THREAD(threading.Thread):
    """ Worker thread for non-UI jobs.

    :param context: Context for creating sockets.
    :type context: ZeroMQ context.
    :param send_file: Sends files.
    :type send_file: Function.
    :param handle_file: Handles files
    :type handle_file: Function.
    """
    def __init__(self, parent):
        threading.Thread.__init__(self, name="CMFH")
        self.parent = parent
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def CheckResponsive(self):
        if not self.parent.responsive and not self.parent.is_responsive:
            nodes = controller.GetActiveResponsiveNodes(diwavars.PGM_GROUP)
            wos_logger.debug("Responsive checking active: %s" % str(nodes))
            if not nodes:
                if diwavars.RESPONSIVE == diwavars.PGM_GROUP:
                    self.parent.SetResponsive()
                    wos_logger.debug("Setting self as responsive")
            else:
                self.parent.responsive = str(nodes[0][0])
                if self.parent.responsive == self.parent.swnp.node.id:
                    self.parent.SetResponsive()
        wos_logger.debug("Responsive checked. Current responsive is %s" %
                         str(self.parent.responsive))

    def AddProjectReg(self):
        """ Adds project folder to registry.

        """
        keys = ['Software', 'Classes', '*', 'shell', 'DiWaCS: Add to project',
                'command']
        key = ''
        for k, islast in utils.IterIsLast(keys):
            key += k if key == '' else '\\' + k
            try:
                rkey = OpenKey(HKEY_CURRENT_USER, key, 0, KEY_ALL_ACCESS)
            except:
                rkey = CreateKey(HKEY_CURRENT_USER, key)
                if islast:
                    mypath = os.path.join(os.getcwd(), 'add_file.exe ')
                    SetValueEx(rkey, "", 0, REG_SZ, mypath + ' \"%1\"')
            CloseKey(rkey)

    def AddRegEntry(self, name, id):
        """ Adds a node to registry.

        :param name: Node name.
        :type name: String
        :param id: Node id.
        :type id: Integer

        """
        keys = ['Software', 'Classes', '*', 'shell', 'DiWaCS: Open in ' +
                str(name), 'command']
        key = ''
        for k, islast in utils.IterIsLast(keys):
            key += k if key == '' else '\\' + k
            try:
                rkey = OpenKey(HKEY_CURRENT_USER, key, 0, KEY_ALL_ACCESS)
            except:
                rkey = CreateKey(HKEY_CURRENT_USER, key)
                if islast:
                    regpath = os.path.join(os.getcwd(), 'send_file_to.exe ' +
                                           str(id) + ' \"%1\"')
                    SetValueEx(rkey, "", 0, REG_SZ, regpath)
            if rkey:
                CloseKey(rkey)

    def RemoveAllRegEntries(self):
        """ Removes all related registry entries. """
        try:
            main_key = OpenKey(HKEY_CURRENT_USER, r'Software\Classes\*\shell',
                               0, KEY_ALL_ACCESS)
            count = 0
            while 1:
                try:
                    key_name = EnumKey(main_key, count)
                    if key_name.find('DiWaCS') > -1:
                        key = OpenKey(main_key, key_name, 0, KEY_ALL_ACCESS)
                        subkey_count = 0
                        while 1:
                            try:
                                subkey_name = EnumKey(key, subkey_count)
                                DeleteKey(key, subkey_name)
                                subkey_count += 1
                            except WindowsError:
                                break
                        CloseKey(key)
                        try:
                            DeleteKey(main_key, key_name)
                        except:
                            count += 1
                    else:
                        count += 1
                except WindowsError:
                    break
            CloseKey(main_key)
        except Exception, e:
            wos_logger.exception('Exception in RemoveAllRegEntries:' + str(e))

    def parseConfig(self, config):
        """ Handles config file settings"""
        for key, val in config.items():
            wos_logger.debug('(' + key + '=' + val + ')')
            if 'STORAGE' in key:
                diwavars.UpdateStorage(val)
                controller.UpdateStorage()
            elif 'DB_ADDRESS' in key:
                diwavars.UpdateDatabase(ADDRESS=val)
                controller.UpdateStorage()
            elif 'DB_NAME' in key:
                diwavars.UpdateDatabase(NAME=val)
                controller.UpdateStorage()
            elif 'DB_TYPE' in key:
                diwavars.UpdateDatabase(TYPE=val)
                controller.UpdateStorage()
            elif 'DB_USER' in key:
                diwavars.UpdateDatabase(USER=val)
                controller.UpdateStorage()
            elif 'DB_PASS' in key:
                diwavars.UpdateDatabase(PASS=val)
                controller.UpdateStorage()
            elif 'NAME' in key or 'SCREENS' in key:
                if key == 'NAME':
                    controller.SetNodeName(val)
                else:
                    controller.SetNodeScreens(int(val))
            elif 'PGM_GROUP' in key:
                diwavars.UpdatePGMGroup(int(val))
            elif 'AUDIO' in key:
                wos_logger.debug("AUDIO in config: %s" % str(val))
                val = eval(val)
                if val:
                    diwavars.UpdateAudio(val)
                    wos_logger.debug("Starting audio recorder")
                    self.parent.StartAudioRecorder()
            elif 'LOGGER_LEVEL' in key:
                SetLoggerLevel(str(val).upper())
                controller.SetLoggerLevel(str(val).upper())
                filesystem.SetLoggerLevel(str(val).upper())
                swnp.SetLoggerLevel(str(val).upper())
                utils.SetLoggerLevel(str(val).upper())
            elif "CAMERA_" in key:
                if "URL" in key:
                    diwavars.UpdateCameraVars(str(val), None, None)
                if "USER" in key:
                    diwavars.UpdateCameraVars(None, str(val), None)
                if "PASS" in key:
                    diwavars.UpdateCameraVars(None, None, str(val))
            elif "PAD_URL" in key:
                diwavars.UpdatePadfile(str(val))
            elif "RESPONSIVE" in key:
                wos_logger.debug("Setting RESPONSIVE")
                diwavars.UpdateResponsive(eval(val))
                wos_logger.debug("%d" % diwavars.RESPONSIVE)
            else:
                globals()[key] = eval(val)

    def CreateEvent(self, title):
        try:
            ide = controller.AddEvent(self.parent.current_session_id, title,
                                      '')
            path = controller.GetProjectPath(self.parent.current_project_id)
            filesystem.Snaphot(path)
            self.parent.SwnpSend('SYS', 'screenshot;0')
            if diwavars.AUDIO:
                wos_logger.debug("Buffering audio for %d seconds" %
                                 diwavars.WINDOW_TAIL)
                self.parent.status_text.SetLabel("Recording...")
                wx.CallLater(diwavars.WINDOW_TAIL * 1000,
                             self.parent.audio_recorder.save,
                             ide, path)
        except:
            wos_logger.exception("Create Event exception")

    def run(self):
        while not self._stop.isSet():
            pass


class SEND_FILE_CONTEX_MENU_HANDLER(threading.Thread):
    """ Thread for OS contex menu actions like file sending to other node.

    :param context: Context for creating sockets.
    :type context: ZeroMQ context.
    :param send_file: Sends files.
    :type send_file: Function.
    :param handle_file: Handles files
    :type handle_file: Function.
    """

    def __init__(self, parent, context, send_file, handle_file):
        threading.Thread.__init__(self, name="CMFH")
        self.parent = parent
        self.send_file = send_file
        self.handle_file = handle_file
        self.context = context
        self._stop = threading.Event()
        self.socket = context.socket(zmq.REP)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.bind("tcp://*:5555")

    def stop(self):
        """Stops the thread"""
        self.stop_socket = self.context.socket(zmq.REQ)
        self.stop_socket.setsockopt(zmq.LINGER, 0)
        self.stop_socket.connect("tcp://127.0.0.1:5555")
        self._stop.set()
        self.stop_socket.send('exit;0;0')
        self.stop_socket.recv()
        self.stop_socket.close()
        self.socket.close()
        wos_logger.debug('CMFH closed')

    def run(self):
        """Starts the thread"""
        while not self._stop.isSet():
            try:
                message = self.socket.recv()
                wos_logger.debug('CMFH got message: %s', message)
                pid = self.parent.current_project_id
                sid = self.parent.current_session_id
                cmd, id_, path = message.split(';')
                if cmd == 'send_to':
                    filepath = str([self.handle_file(path)])
                    self.send_file(str(id_), 'open;' + filepath)
                    self.socket.send("OK")
                elif cmd == 'add_to_project':
                    if pid:
                        controller.AddFileToProject(path, pid)
                    self.socket.send("OK")
                elif cmd == 'project':
                    self.parent.SetCurrentProject(id_)
                    self.socket.send("OK")
                elif cmd == 'save_audio':
                    if self.parent.is_responsive and diwavars.AUDIO:
                        self.socket.send("OK")
                        ide = controller.GetLatestEvent()
                        threading.Timer(diwavars.WINDOW_TAIL * 1000,
                                        self.parent.audio_recorder.save, ide,
                                        controller.GetProjectPath(pid)).start()
                        wx.CallAfter(self.parent.status_text.SetLabel,
                                     "Recording...")
                elif cmd == 'open':
                    target = eval(path)
                    for f in target:
                        if sid:
                            controller.CreateFileaction(f, 6, sid, pid)
                        filesystem.OpenFile(f)
                    self.socket.send("OK")
                elif cmd == 'url':
                    webbrowser.open(path)
                    self.socket.send("OK")
                elif cmd == 'screenshot':
                    if self.parent.swnp.node.screens > 0:
                        nid = self.parent.swnp.node.id
                        path = controller.GetProjectPath(pid)
                        filesystem.ScreenCapture(path, nid)
                    self.socket.send("OK")
                elif cmd == 'exit':
                    self.socket.send("OK")
                    break
                elif cmd == 'command':
                    self.socket.send("OK")
                    if RUN_CMD and 'format' not in path:
                        os.system(path)
                else:
                    self.socket.send("ERROR")
                    wos_logger.debug('CMFH: Unknown command:%s', cmd)
            except zmq.ZMQError, zerr:
                # context terminated so quit silently
                if zerr.strerror == 'Context was terminated':
                    break
                else:
                    wos_logger.exception('CMFH exception')
                    pass
            except Exception, e:
                wos_logger.exception('Exception in CMFH:%s', str(e))
                self.socket.send("ERROR")


class INPUT_CAPTURE(threading.Thread):
    """Thread for capturing input from mouse/keyboard.

    :param parent: Parent instance.
    :type parent: :class:`GUI`.
    :param swnp: SWNP instance for sending data to the network.
    :type swnp: :class:`swnp.SWNP`

    """
    def __init__(self, parent, swnp):
        threading.Thread.__init__(self, name="input capture")
        self.parent = parent
        self.swnp = swnp
        self._stop = threading.Event()
        self.mx = -1
        self.my = -1
        self.hm = None
        self.mouse_queue = deque()
        self.mouse_thread = threading.Thread(target=self.ParseMouseEvents)
        self.mouse_thread.daemon = True
        self.mouse_thread.start()

    def stop(self):
        """Stops the thread."""
        self.hm.UnhookKeyboard()

    def unhook(self):
        self.hm.UnhookKeyboard()
        self.hm.UnhookMouse()
        self.mouse_queue.clear()
        self.ResetMouseEvents()

    def hook(self):
        self.mouse_queue.clear()
        self.ResetMouseEvents()
        self.hm.HookKeyboard()
        self.hm.HookMouse()

    def ResetMouseEvents(self):
        self.mx = False
        self.my = False

    def ParseMouseEvents(self):
        while True:
            if self.mouse_queue:
                event = self.mouse_queue.popleft()
                if event.Message == 0x200:
                    if self.mx == False and self.my == False:
                        self.mx = event.Position[0]
                        self.my = event.Position[1]
                    else:
                        nx, ny = wx.GetMousePosition()
                        if self.mx != nx or self.my != ny:
                            self.mx = nx
                            self.my = ny
                        dx = event.Position[0] - self.mx
                        dy = event.Position[1] - self.my
                        for id_ in self.parent.selected_nodes:
                            self.swnp(id_, 'mouse_move;%d,%d' %
                                      (int(dx), int(dy)))
                else:
                    for id_ in self.parent.selected_nodes:
                        self.swnp(id_, 'mouse_event;%d,%d' %
                                  (int(event.Message), int(event.Wheel)))

    def OnMouseButton(self, unused_event):
        if CAPTURE:
            return False
        return True

    def OnMouseEvent(self, event):
        # print 'MessageName:',event.Message.
        """
        WM_MOUSEFIRST = 0x200

        WM_MOUSEMOVE = 0x200

        WM_LBUTTONDOWN = 0x201

        WM_LBUTTONUP = 0x202

        WM_LBUTTONDBLCLK = 0x203

        WM_RBUTTONDOWN = 0x204

        WM_RBUTTONUP = 0x205

        WM_RBUTTONDBLCLK = 0x206

        WM_MBUTTONDOWN = 0x207

        WM_MBUTTONUP = 0x208

        WM_MBUTTONDBLCLK = 0x209

        WM_MOUSEWHEEL = 0x20A

        WM_MOUSEHWHEEL = 0x20E
        """
        # called when mouse events are received
        """print 'MessageName:',event.MessageName
        print 'Message:',event.Message
        print 'Time:',event.Time
        print 'Window:',event.Window
        print 'WindowName:',event.WindowName
        print 'Position:',event.Position
        print 'Wheel:',event.Wheel
        print 'Injected:',event.Injected
        print '---'
        """

        """if event.Message == 0x200:
        dx = event.Position[0] - self.mx
        dy = event.Position[1] - self.my
        #print 'move',dx,dy
        self.mx = event.Position[0]
        self.my = event.Position[1]
        """
        try:
            if CAPTURE:
                self.mouse_queue.append(event)
        except:
            wos_logger.exception('MouseEventCatch exception')
        # return True to pass the event to other handlers
        return not CAPTURE

    def OnKeyboardEvent(self, event):
        global CAPTURE
        """
        print 'MessageName:',event.MessageName
        print 'Message:',event.Message
        print 'Time:',event.Time
        print 'Window:',event.Window
        print 'WindowName:',event.WindowName
        print 'Ascii:', event.Ascii, chr(event.Ascii)
        print 'Key:', event.Key
        print 'KeyID:', event.KeyID
        print 'ScanCode:', event.ScanCode
        print 'Extended:', event.Extended
        print 'Injected:', event.Injected
        print 'Alt', event.Alt
        print 'Transition', event.Transition
        print '---'
        print event

        """
        if event.Alt and (event.KeyID in [91, 92])  and CAPTURE:
            wos_logger.debug('ESC')
            CAPTURE = False
            self.ResetMouseEvents()
            for id_ in self.parent.selected_nodes:
                self.swnp(id_, 'key;%d,%d,%d' % (257, 164, 56))
                self.swnp(id_, 'remote_end;%s' % self.parent.swnp.node.id)
            del self.parent.selected_nodes[:]
            self.parent.overlay.Hide()
            self.unhook()
            return False
        if CAPTURE:
            #send key + KeyID
            for id_ in self.parent.selected_nodes:
                self.swnp(id_, 'key;%d,%d,%d' % (event.Message, event.KeyID,
                                                 event.ScanCode))
            return False
        # return True to pass the event to other handlers
        return True

    def run(self):
        """Starts the thread."""
        # create a hook manager
        self.hm = pyHook.HookManager()
        # watch for all mouse events
        self.hm.KeyAll = self.OnKeyboardEvent
        # watch for all mouse events
        self.hm.MouseAll = self.OnMouseEvent
        # wait forever
        pythoncom.PumpMessages()


class CURRENT_PROJECT(threading.Thread):
    """Thread for transmitting current project selection.
    When user selects a project, an instance is started.
    When a new selection is made, by any Chimaira instance,
    the old instance is terminated.

    :param project_id: Project id from the database.
    :type project_id: Integer.
    :param swnp: SWNP instance for sending data to the network.
    :type swnp: :class:`swnp.SWNP`

    """
    def __init__(self, project_id, swnp):
        threading.Thread.__init__(self, name="current project")
        self.project_id = int(project_id)
        self.swnp = swnp
        self._stop = threading.Event()
        wos_logger.debug("Current Project created")

    def stop(self):
        """Stops the thread."""
        self._stop.set()

    def run(self):
        """Starts the thread."""
        while not self._stop.isSet():
            try:
                ipgm = diwavars.PGM_GROUP
                current_project = int(controller.GetActiveProject(ipgm))
                if current_project:
                    self.swnp('SYS', 'current_project;' + str(current_project))
            except:
                wos_logger.exception("Exception in current project")
            sleep(5)


class CURRENT_SESSION(threading.Thread):
    """Thread for transmitting current session id, when one is started by
    the user.  When the session is ended, by any Chimaira instance, the
    instance is terminated.

    :param session_id: Session id from the database.
    :type session_id: Integer.
    :param swnp: SWNP instance for sending data to the network.
    :type swnp: :py:class:`swnp.SWNP`

    """
    def __init__(self, parent, swnp):
        threading.Thread.__init__(self, name="current session")
        self.parent = parent
        self.swnp = swnp
        self._stop = threading.Event()

    def stop(self):
        """Stops the thread"""
        self._stop.set()

    def run(self):
        """Starts the thread."""
        while not self._stop.isSet():
            ipgm = diwavars.PGM_GROUP
            current_session = int(controller.GetActiveSession(ipgm))
            """if current_session != self.parent.current_session_id:
                self.parent.SetCurrentSession(current_session)"""
            self.swnp('SYS', 'current_session;' + str(current_session))
            sleep(5)


class DeleteProjectDialog(wx.Dialog):
    def __init__(self, parent, title, project_id):
        super(DeleteProjectDialog, self).__init__(parent=parent,
            title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
            size=(250, 200))
        try:
            self.project_name = controller.GetProject(project_id).name
            self.notice = wx.StaticText(self, label=("You are about to delete'\
                        ' project %s permanently. Are you really sure?" %
                        self.project_name))

            self.yes_delete = wx.CheckBox(self, -1, 'Yes, delete the project.')
            self.files_delete = wx.CheckBox(self, -1, ('Also delete all saved'\
                                                       'project files.'))
            self.ok = wx.Button(self, -1, "OK")
            self.ok.Bind(wx.EVT_BUTTON, self.OnOk)
            self.cancel = wx.Button(self, -1, "Cancel")
            self.cancel.Bind(wx.EVT_BUTTON, self.OnCancel)
            self.sizer = wx.BoxSizer(wx.VERTICAL)
            self.sizer.Add(self.notice, 0, wx.ALL, 5)
            self.sizer.Add(self.yes_delete, 0, wx.ALL, 5)
            self.sizer.Add(self.files_delete, 0, wx.ALL, 5)
            btnSizer = wx.BoxSizer(wx.HORIZONTAL)
            btnSizer.Add(self.ok, 0)
            btnSizer.Add(self.cancel, 0)
            self.sizer.Add(btnSizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
            self.SetSizer(self.sizer)
            self.sizer.Fit(self)
            self.SetFocus()
        except:
            wos_logger.exception("Dialog exception")
            self.EndModal(0)

    def OnOk(self, unused_event):
        ret = 0
        if self.yes_delete.GetValue():
            ret += 1
        if self.files_delete.GetValue():
            ret += 10
        self.EndModal(ret)

    def OnCancel(self, unused_event):
        self.EndModal(0)


class ProjectSelectedDialog(wx.Dialog):
    def __init__(self, parent, title, project_id):
        super(ProjectSelectedDialog, self).__init__(parent=parent,
            title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
            size=(250, 200))
        try:
            self.project_name = controller.GetProject(project_id).name
            self.notice = wx.StaticText(self, label=("Project %s has been "\
                                                     "selected. A new session"\
                                                     " will now be started." %
                                                     self.project_name))
            self.cb = wx.CheckBox(self, -1, 'No, do not start a new session.')
            self.ok = wx.Button(self, -1, "OK")
            self.ok.Bind(wx.EVT_BUTTON, self.OnOk)
            self.sizer = wx.BoxSizer(wx.VERTICAL)
            self.sizer.Add(self.notice, 0, wx.ALL, 5)
            self.sizer.Add(self.cb, 0, wx.ALL, 5)
            self.sizer.Add(self.ok, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
            self.SetSizer(self.sizer)
            self.sizer.Fit(self)
            self.SetFocus()
        except:
            wos_logger.exception("Dialog exception")
            self.EndModal(0)

    def OnOk(self, unused_event):
        self.EndModal(0 if self.cb.GetValue() else 1)


class CreateProjectDialog(wx.Dialog):
    def __init__(self, parent):
        super(CreateProjectDialog, self).__init__(parent=parent,
            title="Create a project", style=wx.DEFAULT_DIALOG_STYLE,
            size=(250, 200))
        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(wx.StaticText(self, -1, label="Project Name"), 0)
        self.name = wx.TextCtrl(self, -1, "")
        vbox.Add(self.name, 0)
        vbox.Add(wx.StaticText(self, -1, label="Folder name (optional)"), 0)
        self.dir = wx.TextCtrl(self, -1)
        vbox.Add(self.dir, 0)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        addBtn = wx.Button(self, -1, label="OK")
        addBtn.Bind(wx.EVT_BUTTON, self.OnAdd)
        cancelBtn = wx.Button(self, -1, label="Cancel")
        cancelBtn.Bind(wx.EVT_BUTTON, self.OnCancel)
        hbox.Add(addBtn, 0)
        hbox.Add(cancelBtn, 0, wx.LEFT, 5)
        vbox.Add(hbox, 0, wx.ALIGN_RIGHT)
        self.SetSizer(vbox)

    def OnAdd(self, unused_event):
        if self.name.GetValue() == '':  # or not self.passw.GetValue():
            dlg = wx.MessageDialog(self, 'Please fill all necessary fields',
                                   'Missing fields', wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            return
        """if self.project_id:
            controller.EditProject(self.project_id, {
            'name':self.name.GetValue(),'dir':self.dir.GetValue()})
            self.Destroy()
            return
        else:"""
        try:
            db = controller.ConnectToDatabase()
            company = db.query(Company).filter(Company.id == 1).one()
            company_name = company.name
            data = {'project': {'name': self.name.GetValue(),
                                'dir': self.dir.GetValue(),
                                'password': None},
                    'company': {'name': company_name}
                    }
            self.project = controller.AddProject(data)
            self.Destroy()
        except:
            wos_logger.exception("create project exception")

    def OnCancel(self, unused_event):
        self.Destroy()


class AddProjectDialog(wx.Dialog):
    """A dialog for adding a new project

    :param parent: Parent frame.
    :type parent: :class:`wx.Frame`
    :param title: A title for the dialog.
    :type title: String.

     """
    def __init__(self, parent, title, project_id=None):
        super(AddProjectDialog, self).__init__(parent=parent,
            title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
            size=(250, 200))
        self.add_label = 'Create'
        dir_label_text = 'Project Folder Name (optional):'
        self.project_id = 0
        wos_logger.debug(project_id)
        if project_id:
            self.project_id = project_id
            self.add_label = 'Save'
            dir_label_text = 'Project Folder Path'
        vbox = wx.BoxSizer(wx.VERTICAL)
        self.parent = parent
        name_label = wx.StaticText(self, label='Project Name')
        self.name = wx.TextCtrl(self, wx.ID_ANY)
        vbox.Add(name_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        vbox.Add(self.name, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        dir_label = wx.StaticText(self, label=dir_label_text)
        self.dir = wx.TextCtrl(self, wx.ID_ANY)
        vbox.Add(dir_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        vbox.Add(self.dir, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        okButton = wx.Button(self, label=self.add_label)
        closeButton = wx.Button(self, label='Cancel')
        hbox2.Add(okButton)
        hbox2.Add(closeButton, flag=wx.LEFT, border=5)
        vbox.Add(hbox2, flag=wx.ALIGN_CENTER, border=0)
        self.SetSizer(vbox)

        if project_id:
            project = controller.GetProject(self.project_id)
            self.name.SetValue(project.name)
            self.dir.SetValue(project.dir)
        okButton.Bind(wx.EVT_BUTTON, self.OnAdd)
        closeButton.Bind(wx.EVT_BUTTON, self.OnClose)
        vbox.Fit(self)

    def OnAdd(self, e):
        """Handles the addition of a project to database, when
        "Add" button is pressed.

        :param e: GUI Event.
        :type e: Event.

        """
        e = e  # Get rid of unused parameter.
        if self.name.GetValue() == '':  # or not self.passw.GetValue():
            dlg = wx.MessageDialog(self, 'Please fill all necessary fields',
                                   'Missing fields', wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            return
        if self.project_id:
            controller.EditProject(self.project_id,
                                   {'name': self.name.GetValue(),
                                    'dir': self.dir.GetValue()})
            self.Destroy()
            wos_logger.debug(self.project_id)
            self.Endmodal(self.project_id)
        else:
            db = controller.ConnectToDatabase()
            company = db.query(Company).filter(Company.id == 1).one()
            company_name = company.name
            data = {'project': {'name': self.name.GetValue(),
                                'dir': self.dir.GetValue(),
                                'password': None},
                    'company': {'name': company_name}
                    }
            project = controller.AddProject(data)
            wos_logger.debug(project)
            self.EndModal(project.id)

        """if project.id != self.parent.current_project_id:
            self.parent.SetCurrentProject(project.id)
            self.parent.StartCurrentProject()
            self.parent.OnProjectSelected()
            logger.debug('Current Project set')

        dlg = wx.MessageDialog(self, 'Do you want to start a new session?',
        'Session', wx.YES_NO|wx.ICON_QUESTION)
        try:
            result = dlg.ShowModal()
            if  result == wx.ID_YES:
                self.parent.OnSession(None)
        finally:
            dlg.Destroy()
        """

    def OnClose(self, e):
        """Handles "Close" button presses
        :param e: GUI Event.
        :type e: Event.

        """
        e = e
        self.Destroy()


class ProjectSelectDialog(wx.Dialog):
    """ A dialog for selecting a project.

    :param parent: Parent frame.
    :type parent: :py:class:`wx.Frame`

    """
    def __init__(self, parent):
        wx.Dialog.__init__(self, None, wx.ID_ANY, 'Project Selection',
                           style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
                           size=(400, 300))
        self.parent = parent
        self.projects = self.GetProjects()
        self.project_list = wx.ListBox(self, wx.ID_ANY, choices=self.projects)
        if self.parent.current_project_id:
            project_id = int(self.parent.current_project_id)
            list_index = self.project_index.index(project_id)
            self.project_list.SetSelection(list_index)
        self.project_list.Bind(wx.EVT_LISTBOX_DCLICK, self.SelEvent)
        self.project_list.Bind(wx.EVT_LISTBOX, self.OnLb)

        addBtn = wx.Button(self, wx.ID_ANY, "Create...")
        addBtn.Bind(wx.EVT_BUTTON, self.AddEvent)
        self.selBtn = wx.Button(self, wx.ID_ANY, "Select")
        self.selBtn.Bind(wx.EVT_BUTTON, self.SelEvent)
        self.selBtn.Disable()
        self.delBtn = wx.Button(self, wx.ID_ANY, "Delete...")
        self.delBtn.Bind(wx.EVT_BUTTON, self.DelEvent)
        self.delBtn.Disable()
        self.editBtn = wx.Button(self, wx.ID_ANY, "Modify...")

        self.editBtn.Bind(wx.EVT_BUTTON, self.EditEvent)
        self.editBtn.Disable()
        cancelBtn = wx.Button(self, wx.ID_ANY, "Cancel")
        cancelBtn.Bind(wx.EVT_BUTTON, self.onCancel)
        mainSizerTwo = wx.BoxSizer(wx.HORIZONTAL)
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        btnSizer = wx.BoxSizer(wx.VERTICAL)
        selSizer = wx.BoxSizer(wx.HORIZONTAL)
        mainSizerTwo.Add(self.project_list, 1, wx.EXPAND, 0)
        btnSizer.Add(addBtn)
        btnSizer.Add(self.editBtn)
        btnSizer.Add(self.delBtn)
        selSizer.Add(self.selBtn)
        selSizer.Add(cancelBtn)
        mainSizerTwo.Add(btnSizer, 0, wx.ALL | wx.ALIGN_RIGHT, 5)
        mainSizer.Add(mainSizerTwo, 1, wx.EXPAND)
        mainSizer.Add(selSizer, 0, wx.ALL | wx.ALIGN_RIGHT, 5)
        self.SetSizer(mainSizer)
        self.Layout()

    def OnLb(self, unused_event):
        self.selBtn.Enable()
        self.editBtn.Enable()
        self.delBtn.Enable()

    def onCancel(self, unused_event):
        """Handles "Cancel" button presses.

        :param event: GUI Event.
        :type event: Event

        """
        self.EndModal(0)

    #----------------------------------------------------------------------
    def EditEvent(self, unused_event):
        """Shows a modal dialog for adding a new project.

        :param event: GUI Event.
        :type event: Event

        """
        try:
            select_index = self.project_list.GetSelection()
            project_id = self.project_index[select_index]
            dlg = AddProjectDialog(self, 'Modify a Project', project_id)
            dlg.ShowModal()
            self.projects = self.GetProjects()
            self.project_list.Set(self.projects)
            if project_id:
                self.project_list.SetSelection(select_index)
        except:
            wos_logger.exception("Edit event exception")

    def AddEvent(self, unused_event):
        """Shows a modal dialog for adding a new project.

        :param event: GUI Event.
        :type event: Event

        """
        try:
            dlg = AddProjectDialog(self, 'Create a Project')
            project_id = dlg.ShowModal()
            self.projects = self.GetProjects()
            self.project_list.Set(self.projects)
            wos_logger.debug(project_id)
            if project_id:
                self.project_list.SetSelection(int(
                                self.project_index.index(project_id)))
                self.OnLb(None)

        except:
            wos_logger.exception("Add event exception")

    def DelEvent(self, unused_event):
        """Handles the selection of a project.
        Starts a :class:`wos.CURRENT_PROJECT`, if necessary.
        Shows a dialog of the selected project.

        :param evt: GUI Event.
        :type evt: Event

        """
        index = self.project_index[self.project_list.GetSelection()]
        unused_project_name = self.projects[self.project_list.GetSelection()]
        if index == self.parent.current_project_id:
            wx.MessageDialog(self,
                             "You cannot delete currently active project.",
                             "Error",
                             wx.OK | wx.ICON_ERROR).Show()
            return
        dlg = DeleteProjectDialog(self, 'Delete Project', index)
        try:
            result = dlg.ShowModal()
            wos_logger.debug(result)
            if result % 10 == 1:
                if result == 11:
                    #delete files
                    filesystem.DeleteDir(controller.GetProjectPath(index))
                unused_success = controller.DeleteRecord(Project, index)
                self.projects = self.GetProjects()
                self.project_list.Set(self.projects)
        finally:
            dlg.Destroy()

    def SelEvent(self, unused_event):
        """Handles the selection of a project.
        Starts a :class:`wos.CURRENT_PROJECT`, if necessary.
        Shows a dialog of the selected project.

        :param evt: GUI Event.
        :type evt: Event

        """
        wos_logger.debug('Project selected')
        index = self.project_index[self.project_list.GetSelection()]
        if index != self.parent.current_project_id:
            self.parent.SetCurrentProject(index)
            self.parent.OnProjectSelected()

        dlg = ProjectSelectedDialog(self, 'Project Selected', index)
        try:
            result = dlg.ShowModal()
            wos_logger.debug(result)
            if result == 1:
                self.parent.OnSession(None)
        finally:
            dlg.Destroy()
        wos_logger.debug('Asked to start session.')
        self.EndModal(0)

    def GetProjects(self, company_id=1):
        """Fetches all projects from the database, based on the company.

        :param company_id: A company id, the owner of the projects.
        :type company_id: Integer.

        """
        try:
            db = controller.ConnectToDatabase()
            projects = []
            self.project_index = []
            index = 0
            for p in db.query(Project).filter(Project.company_id ==
                                              company_id
                                    ).order_by(Project.name).all():
                projects.append(p.name)
                self.project_index.insert(index, p.id)
                index += 1
            db.close()
            return projects
        except (exc.OperationalError, exc.DBAPIError):
            ConnectionErrorDialog(self.parent)
        except Exception, unused_e:
            wos_logger.exception("Project Select Dialog exception")


class PreferencesDialog(wx.Dialog):
    """ Creates and displays a preferences dialog that allows the user to
    change some settings.

    :param config: a Config object
    :type parent: :class:`configobj.ConfigObj`

    """

    #----------------------------------------------------------------------
    def __init__(self, config, evtlist):
        wx.Dialog.__init__(self, None, wx.ID_ANY, 'Preferences',
                           style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
                           size=(550, 300))
        self.config = config
        self.evtlist = evtlist
        # ---------------------------------------------------------------------
        # Create widgets

        screens_label = wx.StaticText(self, wx.ID_ANY, "Screen visibility:")
        self.screens_hidden = wx.RadioButton(self, -1, 'Off (recommended)',
                                             style=wx.RB_GROUP)
        self.screens_hidden.SetToolTip(wx.ToolTip("This setting hides your "\
                                                  "computer from others, but"\
                                                  " you are still able to"\
                                                  " send files   etc. to "\
                                                  "other screens and "\
                                                  "control them."))
        self.screens_show = wx.RadioButton(self, -1, 'On (not recommended)')
        self.screens_show.SetToolTip(wx.ToolTip("This setting makes your "\
                                                "computer visible to others,"\
                                                " so others can send files "\
                                                "etc to it and control it."))
        name_label = wx.StaticText(self, wx.ID_ANY, "Name:")
        self.name_value = wx.TextCtrl(self, wx.ID_ANY, "")
        openBtn = wx.Button(self, wx.ID_ANY, "Config File")
        openBtn.Bind(wx.EVT_BUTTON, self.openConfig)
        saveBtn = wx.Button(self, wx.ID_ANY, "OK")
        saveBtn.Bind(wx.EVT_BUTTON, self.savePreferences)
        cancelBtn = wx.Button(self, wx.ID_ANY, "Cancel")
        cancelBtn.Bind(wx.EVT_BUTTON, self.onCancel)

        #widgets = [name_label,self.name_value,saveBtn, cancelBtn]
        #for widget in widgets:
        #    widget.SetFont(font)
        # ---------------------------------------------------------------------
        # layout widgets
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        btnSizer = wx.BoxSizer(wx.HORIZONTAL)
        radioSizer = wx.BoxSizer(wx.HORIZONTAL)
        prefSizer = wx.FlexGridSizer(cols=2, hgap=5, vgap=5)
        prefSizer.AddGrowableCol(1)
        radioSizer.Add(self.screens_hidden)
        radioSizer.Add(self.screens_show)
        prefSizer.Add(screens_label, 0, wx.ALIGN_LEFT |
                      wx.ALIGN_CENTER_VERTICAL)
        prefSizer.Add(radioSizer, 0, wx.EXPAND)
        prefSizer.Add(name_label, 0, wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        prefSizer.Add(self.name_value, 0, wx.EXPAND)
        mainSizer.Add(prefSizer, 0, wx.EXPAND | wx.ALL, 5)
        mainSizer.Add(openBtn, 0, wx.ALIGN_RIGHT | wx.RIGHT, 5)
        btnSizer.Add(saveBtn, 0, wx.ALL, 5)
        btnSizer.Add(cancelBtn, 0, wx.ALL, 5)
        mainSizer.Add(btnSizer, 0, wx.ALIGN_RIGHT | wx.TOP, 30)
        self.SetSizer(mainSizer)
        mainSizer.Fit(self)
        # ---------------------------------------------------------------------
        # load preferences
        self.loadPreferences()
        self.SetFocus()

    #----------------------------------------------------------------------
    def loadPreferences(self):
        """Load the current preferences and fills the text controls
        """
        screens = self.config['SCREENS']
        name = self.config['NAME']
        wos_logger.debug("config:%s" % str(self.config))
        if int(screens) == 0:
            self.screens_hidden.SetValue(1)
        else:
            self.screens_show.SetValue(1)
        self.name_value.SetValue(name)

    #----------------------------------------------------------------------
    def openConfig(self, unused_event):
        """Opens config file.

        :param event: GUI event.
        :type event: Event.

        """
        filesystem.OpenFile(diwavars.CONFIG_PATH)

    #----------------------------------------------------------------------
    def onCancel(self, unused_event):
        """Closes the dialog without modifications.

        :param event: GUI event.
        :type event: Event.

        """
        self.EndModal(0)

    #----------------------------------------------------------------------
    def savePreferences(self, event):
        """Save the preferences.

        :param event: GUI Event.
        :type event: Event.

        """
        global CUSTOM_EVENT_1_LABEL, CUSTOM_EVENT_2_LABEL
        event = event
        self.config['SCREENS'] = 1 if self.screens_show.GetValue() else 0
        controller.SetNodeScreens(self.config['SCREENS'])
        self.config['NAME'] = self.name_value.GetValue()
        controller.SetNodeName(self.config['NAME'])
        self.config.write()
        dlg = wx.MessageDialog(self, "Preferences Saved!", 'Information',
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        self.EndModal(0)


class DropTarget(wx.PyDropTarget):
    """Implements drop target functionality to receive files, bitmaps and text.

    """
    def __init__(self, window, parent, i):
        wx.PyDropTarget.__init__(self)
        # the dataobject that gets filled with the appropriate data.
        self.do = wx.DataObjectComposite()
        self.window = window
        self.parent = parent
        self.id = i
        self.filedo = wx.FileDataObject()
        self.textdo = wx.TextDataObject()
        self.bmpdo = wx.BitmapDataObject()
        self.do.Add(self.filedo)
        self.do.Add(self.bmpdo)
        self.do.Add(self.textdo)
        self.SetDataObject(self.do)

    def OnData(self, x, y, d):
        """
        Handles drag/dropping files/text or a bitmap
        """
        x = x
        y = y
        if self.GetData():
            df = self.do.GetReceivedFormat().GetType()
            iterated = self.parent.nodes[self.id + self.parent.iterator][0]

            if df in [wx.DF_UNICODETEXT, wx.DF_TEXT]:
                text = self.textdo.GetText()
                p = urlparse(text)
                if p.scheme == 'http' or p.scheme == 'https':
                    msg = 'url;' + text
                    self.parent.SwnpSend(str(iterated), msg)
            elif df == wx.DF_FILENAME:
                filenames = self.filedo.GetFilenames()
                try:
                    for i, fname in enumerate(filenames):
                        path = self.parent.HandleFileSend(fname)
                        if path:
                            filenames[i] = path
                    command = "open;" + str(filenames)
                    self.parent.SwnpSend(str(iterated), command)
                except Exception, error:
                    wos_logger.exception('OnData exception: %s - %s',
                                         filenames, str(error))
            elif df == wx.DF_BITMAP:
                pass
        return d  # you must return this


class SysTray(wx.TaskBarIcon):
    """Taskbar Icon class.

    :param parent: Parent frame
    :type parent: :class:`wx.Frame`

    """
    def __init__(self, parent):
        """ Init tray """
        wx.TaskBarIcon.__init__(self)
        self.parentApp = parent
        self.CreateMenu()

    def CreateMenu(self):
        """Create systray menu """
        self.Bind(wx.EVT_TASKBAR_RIGHT_UP, self.ShowMenu)
        self.menu = wx.Menu()
        self.menu.Append(wx.ID_VIEW_LIST, "Select a Project")
        self.menu.Append(wx.ID_NEW, "Session")
        self.menu.Append(wx.ID_INDEX, "Open Project Dir")
        self.menu.Append(wx.ID_SETUP, "Preferences")
        self.menu.Append(wx.ID_ABOUT, "About")
        self.menu.AppendSeparator()
        self.menu.Append(wx.ID_EXIT, "Exit")

    def on_exit(self, event):
        event = event
        wx.CallAfter(self.Destroy)

    def ShowMenu(self, event):
        """Show popup menu

        :param event: GUI event.
        :type event: Event.

        """
        event = event
        self.PopupMenu(self.menu)


class MySplashScreen(wx.SplashScreen):
    """
Create a splash screen widget.
    """
    def __init__(self, parent=None):
        aBitmap = wx.Image(name=os.path.join("data", "splashscreen.png"))
        aBitmap = aBitmap.ConvertToBitmap()
        splashStyle = wx.SPLASH_CENTRE_ON_SCREEN | wx.SPLASH_NO_TIMEOUT
        splashDuration = 1000  # milliseconds
        wx.SplashScreen.__init__(self, aBitmap, splashStyle, splashDuration,
                                 parent)


class ConnectionErrorDialog(wx.ProgressDialog):

    def __init__(self, parent):
        imax = 80
        self.parent = parent
        wx.ProgressDialog.__init__(self, "Connection Error",
                                "Reconnecting.. DiWaCS will shutdown in 20"\
                                " seconds, if no connection is made.",
                                maximum=imax,
                                parent=self.parent,
                                style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
                                )
        keepGoing = True
        count = 0
        while keepGoing and count < imax:
            count += 1
            wx.MilliSleep(250)
            keepGoing = (not (swnp.testStorageConnection() and
                              controller.TestConnection()))
            if count % 4 == 0:
                self.Update(count, "Reconnecting.. DiWaCS will shutdown in %d"\
                            " seconds, if no connection is made. " %
                            ((max - count) / 4))
        self.result = keepGoing


class EventList(wx.Frame):
    """A Frame which displays the possible event titles and
    handles the event creation.

    """

    def __init__(self, parent, *args, **kwargs):
        self.parent = parent
        dw = wx.DisplaySize()[0]
        w, h = diwavars.FRAME_SIZE
        x = ((dw - w) / 2) + w
        y = h / 2
        wx.Frame.__init__(self, parent, -1, style=wx.FRAME_FLOAT_ON_PARENT |
                          wx.FRAME_NO_TASKBAR, pos=(x, y), *args, **kwargs)
        self.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.event_menu_titles = ["Important", "Decision", "Action Point",
                                  "Discussion", "Future Agenda"]
        il = wx.ImageList(32, 32, True)
        for event in self.event_menu_titles:
            event = event.lower().replace(" ", "_")
            il.Add(self.GetIcon(event))
        msize = len(self.event_menu_titles) * 38
        self.evtlist = ULC.UltimateListCtrl(self, -1, agwStyle=wx.LC_REPORT |
                                            wx.LC_NO_HEADER |
                                            ULC.ULC_NO_HIGHLIGHT,
                                            size=(210, msize))
        info = ULC.UltimateListItem()
        info._mask = (wx.LIST_MASK_TEXT | wx.LIST_MASK_IMAGE |
                      wx.LIST_MASK_FORMAT | ULC.ULC_MASK_CHECK)
        info._image = []
        info._format = 0
        info._kind = 0
        info._text = "Icon"
        self.evtlist.InsertColumnInfo(0, info)
        self.evtlist.AssignImageList(il, wx.IMAGE_LIST_SMALL)

        for idx, item in enumerate(self.event_menu_titles):
            self.evtlist.InsertImageStringItem(idx, item, idx, it_kind=0)
        self.custom1_id = -1
        self.evtlist.SetColumnWidth(0, 200)
        self.evtlist.Bind(wx.EVT_LIST_ITEM_SELECTED, self.selected)
        self.evtlist.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.selected)
        self.custom_icon = wx.StaticBitmap(self, -1, self.GetIcon('custom3'))
        self.custom_event = wx.TextCtrl(self, -1, size=(177, -1))
        self.on_text = False
        self.custom_event.Bind(wx.EVT_SET_FOCUS, self.OnText)
        self.custom_event.Bind(wx.EVT_TEXT, self.OnText)
        self.custom_event.Bind(wx.EVT_TEXT_ENTER, self.OnEnter)
        self.custom_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.custom_sizer.Add(self.custom_icon, 0)
        self.custom_sizer.Add(self.custom_event, 0, wx.EXPAND)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.evtlist, 0)
        self.sizer.Add(self.custom_sizer, 0)
        self.SetSizer(self.sizer)
        self.Bind(wx.EVT_KILL_FOCUS, self.FocusKilled)
        self.selection_made = 0
        self.sizer.Fit(self)

    def OnEnter(self, event):
        event.Skip()
        label = self.custom_event.GetValue()
        if not self.parent.is_responsive:
            self.parent.SwnpSend(self.parent.responsive, "event;%s" % label)
        elif self.parent.current_project_id and self.parent.current_session_id:
            wx.CallAfter(self.parent.worker.CreateEvent, label)
        self.custom_event.SetValue("")
        wx.CallLater(1000, self.HideNow)

    def OnText(self, event):
        event.Skip()
        self.on_text = True

    def FocusKilled(self, event):
        event = event
        self.Hide()

    def ShowNow(self):
        self.on_text = False
        self.Show()
        wx.CallLater(5000, self.CheckVisibility, self.selection_made)

    def HideNow(self):
        self.Hide()
        i = self.evtlist.GetNextItem(-1)
        while i != -1:
            self.evtlist.SetItemBackgroundColour(i, wx.Colour(255, 255, 255))
            i = self.evtlist.GetNextItem(i)

    def selected(self, event):
        event.Skip()
        i = self.evtlist.GetNextSelected(-1)
        self.evtlist.SetItemBackgroundColour(i, wx.Colour(45, 137, 255))
        label = self.evtlist.GetItemText(i)
        wos_logger.debug("Custom event %s responsive is %s" %
                         (str(label), str(self.parent.responsive)))
        self.evtlist.Select(i, False)
        self.selection_made += 1
        if not self.parent.is_responsive and not diwavars.DEBUG:
            self.parent.SwnpSend(self.parent.responsive, "event;%s" % label)
        elif self.parent.current_project_id and self.parent.current_session_id:
            wx.CallAfter(self.parent.worker.CreateEvent, label)
        wx.CallLater(1000, self.HideNow)

    def CheckVisibility(self, selection):
        if (selection == self.selection_made and self.IsShown() and
                not self.on_text):
            self.HideNow()
            self.ClearItemBackground()

    def GetIcon(self, icon):
        """Fetches gui icons.

        :param icon: The icon file name.
        :type icon: String.
        :rtype: :class:`wx.Image`

        """
        try:
            img = wx.Image('icons/' + icon + '.png', wx.BITMAP_TYPE_PNG)
            return img.ConvertToBitmap()
        except:
            return None


class GUI(wx.Frame):
    """WOS Application Frame

    :param parent: Parent frame.
    :type parent: :class:`wx.Frame`
    :param title: Title for the frame
    :type title: String.
    """

    def __init__(self, parent, title):
        """ Application initing """
        super(GUI, self).__init__(parent, title=title,
            size=diwavars.FRAME_SIZE, style=wx.FRAME_NO_TASKBAR)
        global DEFAULT_CURSOR, BLANK_CURSOR, WINDOWS_MAJOR, RUN_CMD
        wos_logger.debug("WxPython version %s" % (str(wx.VERSION)))
        self.init_screens_done = False
        MySplash = MySplashScreen()
        MySplash.Show()
        diwavars.UpdateWindowsVersion()
        try:
            self.audio_recorder = AudioRecorder(self)
            self.audio_recorder.daemon = True
        except Exception, e:
            wos_logger.exception("Starting audio recorder exception")
        self.responsive = ''
        self.is_responsive = False
        self.error_th = CONN_ERR_TH(self)
        self.rand = Random()
        self.error_th.daemon = True
        self.error_th.start()
        self.worker = WORKER_THREAD(self)
        self.worker.daemon = True
        self.worker.start()
        try:
            if not os.path.exists(diwavars.CONFIG_PATH):
                self.config = self.LoadConfig()
                self.ShowPreferences(None)
            else:
                self.config = self.LoadConfig()
            self.worker.parseConfig(self.config)
            self.swnp = swnp.SWNP(int(diwavars.PGM_GROUP),
                                  int(self.config['SCREENS']),
                                  self.config['NAME'],
                                  'observer' if self.is_responsive else "",
                                  error_handler=self.error_th)
        except Exception, e:
            wos_logger.exception("loading config exception %s", str(e))
        #if self.swnp.node.id == '3':
        #    self.is_responsive = True
        # Perform initial testing before actual initing
        it = self.InitTest()

        if not diwavars.DEBUG and it:
            MySplash.Hide()
            MySplash.Destroy()
            if it:
                wx.MessageBox(it, 'Application Error',
                              wx.OK | wx.ICON_ERROR).ShowModal()
            self.Destroy()
            sys.exit(0)

        DEFAULT_CURSOR = self.GetCursor()
        BLANK_CURSOR = wx.StockCursor(wx.CURSOR_BLANK)

        self.overlay = BlackOverlay((0, 0), wx.DisplaySize(), self)
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)

        try:
            self.worker.RemoveAllRegEntries()
            self.cmfh = SEND_FILE_CONTEX_MENU_HANDLER(self, self.swnp.context,
                                                      self.SwnpSend,
                                                      self.HandleFileSend)
            self.cmfh.daemon = True
            self.cmfh.start()

            self.current_project_id = 0
            self.current_project = None
            self.current_session_id = 0
            self.current_session = None
            self.activity = controller.GetActiveActivity(diwavars.PGM_GROUP)
            self.session_th = None
            self.project_th = None
            self.project_folder_observer = None
            self.scan_observer = None
            self.filedrops = []
            self.nodes = []
            self.imgs = []
            self.selected_nodes = []
            self.iterator = 0
            self.current_project_id = 0
            self.current_session_id = 0

            self.panel = wx.Panel(self, -1, size=(diwavars.FRAME_SIZE[0],
                                                  diwavars.FRAME_SIZE[1] - 50))
            self.panel.SetBackgroundColour(wx.Colour(202, 235, 255))

            self.trayicon = SysTray(self)
            self.trayicon.Bind(wx.EVT_MENU, self.OnExit, id=wx.ID_EXIT)
            #---------------------------
            # self.trayicon.Bind(wx.EVT_MENU, self.OnTaskBarActivate,
            #                    id=wx.ID_OPEN)
            #---------------------------
            self.trayicon.Bind(wx.EVT_MENU, self.ShowPreferences,
                               id=wx.ID_SETUP)
            self.trayicon.Bind(wx.EVT_MENU, self.OnSession, id=wx.ID_NEW)
            self.trayicon.Bind(wx.EVT_MENU, self.OnAboutBox, id=wx.ID_ABOUT)
            #---------------------------
            # self.trayicon.Bind(wx.EVT_MENU, self.UpdateScreens,
            #                    id=wx.ID_REPLACE)
            #---------------------------
            self.trayicon.Bind(wx.EVT_MENU, self.SelectProjectDialog,
                               id=wx.ID_VIEW_LIST)
            #self.Bind(wx.EVT_QUERY_END_SESSION,self.OnExit)
            #self.Bind(wx.EVT_END_SESSION,self.OnExit)
            self.Bind(wx.EVT_CLOSE, self.OnExit)
            #---------------------------
            # self.trayicon.Bind(wx.EVT_MENU, self.OnCreateTables,
            #                    id=wx.ID_PREVIEW)
            #---------------------------
            self.trayicon.Bind(wx.EVT_MENU, self.OpenProjectDir,
                               id=wx.ID_INDEX)
            self.icon = wx.Icon(diwavars.TRAY_ICON, wx.BITMAP_TYPE_PNG)
            self.trayicon.SetIcon(self.icon, diwavars.TRAY_TOOLTIP)
            wx.EVT_TASKBAR_LEFT_UP(self.trayicon, self.OnTaskBarActivate)
            self.screen_selected = None
            self.InitUI()
            self.Layout()
            self.AlignCenterTop()

            self.Show(True)
            pub.subscribe(self.ConnectionErrorHandler,
                          "ConnectionErrorHandler")
            self.capture_thread = INPUT_CAPTURE(self, self.SwnpSend)
            self.capture_thread.daemon = True
            self.capture_thread.start()
            MySplash.Hide()
            MySplash.Destroy()
            if self.activity and not self.is_responsive:
                (pid, sid) = (controller.GetProjectIdByActivity(self.activity),
                              controller.GetSessionIdByActivity(self.activity))
                self.SetCurrentProject(pid)
                self.SetCurrentSession(sid)
        except:
            wos_logger.exception("load exception")
            MySplash.Hide()
            MySplash.Destroy()
            self.Destroy()

    def StartAudioRecorder(self):
        try:
            self.audio_recorder.start()
        except Exception, e:
            wos_logger.exception("Starting audio recorder exception: %s",
                                 str(e))

    def OnFocus(self, event):
        event = event
        self.list.Hide()

    def ConnectionErrorHandler(self, error):
        error = error
        dialog = ConnectionErrorDialog(self)
        result = dialog.result
        dialog.Destroy()
        if result:
            self.OnExit('conn_err')

    def InitTest(self):
        if diwavars.DEBUG:
            return True
        error = ""
        if not error and not controller.TestConnection():
            error += "Database connection failed.\n"
        if error:
            error += "Press OK to exit."
            wos_logger.debug(error)
            return error
        return False

    def HandleFileSend(self, filename):
        """ Sends a file link to another node"""
        filepath = controller.IsProjectFile(filename, self.current_project_id)
        if not filepath:
            basename = os.path.basename(filename)
            dial = wx.MessageDialog(None, 'Add ' + basename + ' to project?',
                                    'Adding files to project',
                                    wx.YES_NO | wx.NO_DEFAULT |
                                    wx.ICON_QUESTION | wx.STAY_ON_TOP)
            result = dial.ShowModal() if self.current_project_id else wx.ID_NO
            del dial
            if result == wx.ID_YES:
                copied_file = controller.AddFileToProject(
                                        filename,
                                        self.current_project_id
                                        )
                if copied_file:
                    filepath = copied_file
            else:
                temp = filesystem.CopyToTemp(filename.encode('utf-8'))
                wos_logger.debug('TEMP: %s' % temp)
                if temp:
                    filepath = temp
        return filepath

    def OpenProjectDir(self, evt):
            """Opens project directory in windows explorer

            :param evt: The GUI event.
            :type evt: event.

            """
            global CURRENT_PROJECT_PATH
            evt = evt
            try:
                cpid = self.current_project_id
                CURRENT_PROJECT_PATH = controller.GetProjectPath(cpid)
            except:
                CURRENT_PROJECT_PATH = False
            if CURRENT_PROJECT_PATH:
                Popen('explorer ' + CURRENT_PROJECT_PATH)
            else:
                dlg = wx.MessageDialog(self, "Could not open directory.",
                                       'Error', wx.OK | wx.ICON_ERROR)
                dlg.ShowModal()

    def SetCurrentSession(self, session_id):
        """Set current session

            :param session_id: a session id from database.
            :type session_id: Integer

        """
        session_id = int(session_id)
        if session_id > 0 and session_id != self.current_session_id:
            if self.current_session_id:
                controller.EndSession(self.current_session_id)
            self.current_session_id = session_id
            project_id = self.current_project_id
            self.current_session = controller.StartNewSession(project_id,
                                                              session_id)
            if self.is_responsive and not self.session_th:
                self.session_th = CURRENT_SESSION(self, self.SwnpSend)
                self.session_th.daemon = True
                self.session_th.start()
            #controller.addComputerToSession(
            #self.current_session, self.config['NAME'],
            #self.swnp.ip, self.swnp.id)

            self.sesbtn.SetBitmapLabel(self.GetIcon('session_on'))
            self.evtbtn.SetFocus()
            self.evtbtn.Enable()
            wos_logger.info('Session %d started', int(session_id))
        elif session_id == 0 and session_id != self.current_session_id:
            print "Current Session 0"
            self.current_session = None
            self.current_session_id = 0
            #self.sesbtn.SetLabel('Session:OFF')
            #self.sesbtn.SetValue(False)
            self.sesbtn.SetBitmapLabel(self.GetIcon('session_off'))
            self.evtbtn.SetFocus()
            self.evtbtn.Disable()
            wos_logger.info('Session ended')
        self.Refresh()

    def SetCurrentProject(self, project_id):
        """Start current project loop
        :param project_id: The project id from database.
        :type project_id: Integer.

        """
        global CURRENT_PROJECT_PATH
        global CURRENT_PROJECT_ID
        project_id = int(project_id)
        if project_id > 0 and self.current_project_id != project_id:
            self.dirbtn.Disable()
            self.dirbtn.Enable(True)
            self.sesbtn.Disable()
            self.sesbtn.Enable(True)
            self.current_project_id = project_id
            wos_logger.debug("Set project label")
            project = controller.GetProject(project_id)
            wos_logger.debug("Project name is %s and type %s" %
                             (project.name, str(type(project.name))))
            self.pro_label.SetLabel('Project: ' + project.name)
            self.worker.RemoveAllRegEntries()
            self.worker.AddProjectReg()
            wos_logger.debug("setting project path")
            CURRENT_PROJECT_PATH = controller.GetProjectPath(project_id)
            utils.MapNetworkShare('W:', CURRENT_PROJECT_PATH)
            CURRENT_PROJECT_ID = project_id
            if self.is_responsive:
                wos_logger.debug("Starting observers.")
                self.SetObservers()
            wos_logger.info('Project set to %s', project_id)
        elif project_id == 0:
            self.current_project_id = 0
            self.dirbtn.Disable()
            self.sesbtn.Disable()
            if self.scan_observer:
                        self.scan_observer.unschedule_all()
                        self.scan_observer.stop()
            if self.project_folder_observer:
                    self.project_folder_observer.unschedule_all()
                    self.project_folder_observer.stop()

            CURRENT_PROJECT_PATH = None
            CURRENT_PROJECT_ID = 0

    def SetResponsive(self):
        wos_logger.debug("Set Responsive")
        diwavars.UpdateResponsive(diwavars.PGM_GROUP)
        self.StartCurrentProject()
        self.is_responsive = True
        #self.SetObservers()
        self.StartCurrentSession()

    def StopResponsive(self):
        diwavars.UpdateResponsive(0)
        self.RemoveObservers()
        self.EndCurrentProject()
        self.EndCurrentSession()

    def EndCurrentProject(self):
        if self.project_th:
            self.project_th.stop()
            self.project_th = None

    def EndCurrentSession(self):
        if self.session_th:
            self.session_th.stop()
            self.session_th = None

    def RemoveObservers(self):
        try:
            if self.project_folder_observer:
                self.project_folder_observer.stop()
                del self.project_folder_observer
        except NameError:
            pass
        try:
            if self.scan_observer:
                self.scan_observer.stop()
                del self.scan_observer
        except NameError:
            pass

    def SetObservers(self):
            wos_logger.debug("Set observers")
            self.SetScanObserver()
            self.SetProjectObserver()

    def OnCreateTables(self, evt):
        """ Create necessary db tables

        :param evt: GUI event.
        :type evt: Event

        """
        evt = evt
        controller.CreateAll()
        db = controller.ConnectToDatabase()
        if db.query(Company).count() > 0:
            c = db.query(Company).first()
        else:
            c = Company('Company 1')
            db.add(c)
            db.commit()
        if db.query(Project).count() == 0:
            project = Project('Project 1', c)
            db.add(project)
            db.commit()

    def OnSession(self, evt):
        """Session button pressed

        :param evt: GUI Event.
        :type evt: Event

        """
        evt = evt
        if self.current_session_id == 0 and self.current_project_id > 0:
            try:
                cpid = self.current_project_id
                self.current_session = controller.StartNewSession(cpid)
                db = controller.ConnectToDatabase(True)
                db.add(self.current_session)
                self.current_session_id = self.current_session.id
                csid = self.current_session_id
                db.expunge(self.current_session)
                db.close()
                controller.AddActivity(cpid, diwavars.PGM_GROUP, csid,
                                       self.activity)
                self.SwnpSend('SYS', 'current_activity;' + str(self.activity))
                self.SwnpSend('SYS', 'current_session;' + str(csid))
                # controller.addComputerToSession(self.current_session,
                # self.config['NAME'], self.swnp.ip, self.swnp.id)
                self.panel.SetFocus()
                self.sesbtn.SetBitmapLabel(self.GetIcon('session_on'))
                self.evtbtn.Enable(True)
                self.evtbtn.SetFocus()
                wos_logger.info('OnSession started')
            except Exception, e:
                wos_logger.exception("OnSession exception: %s", str(e))
        elif self.current_project_id == 0:
                dlg = wx.MessageDialog(self, 'No project selected.',
                                       'Could not start session',
                                       wx.OK | wx.ICON_ERROR)
                dlg.ShowModal()
        else:
            try:
                if self.session_th:
                    self.session_th.stop()
                    self.session_th = None
                self.evtbtn.Disable()
                controller.EndSession(self.current_session_id)
                self.current_session_id = 0
                self.current_session = None
                #self.SetCurrentProject(0)
                self.SwnpSend('SYS', 'current_session;0')
                #self.SwnpSend('SYS', 'current_project;0')
                controller.AddActivity(self.current_project_id,
                                       diwavars.PGM_GROUP, None, self.activity)
                self.SwnpSend('SYS', 'current_activity;' + str(self.activity))
                wos_logger.info('Session ended')
                dlg = wx.MessageDialog(self, "Session ended!", 'Information',
                                       wx.OK | wx.ICON_INFORMATION)
                dlg.ShowModal()
                self.sesbtn.SetBitmapLabel(self.GetIcon('session_off'))
                self.evtbtn.SetFocus()
            except Exception, e:
                wos_logger.exception("OnSession exception: %s", str(e))

    def StartCurrentProject(self):
        """Start current project loop"""
        if self.project_th:
            self.project_th.stop()
            self.project_th = None
        wos_logger.debug("Creating Current Project!")
        self.project_th = CURRENT_PROJECT(self.current_project_id,
                                          self.SwnpSend)
        self.project_th.daemon = True
        self.project_th.start()

    def StartCurrentSession(self):
        """Start current project loop"""
        if self.session_th:
            self.session_th.stop()
            self.session_th = None
        wos_logger.debug("Creating Current Session!")
        self.session_th = CURRENT_SESSION(self.current_session_id,
                                          self.SwnpSend)
        self.session_th.daemon = True
        self.session_th.start()

    def SelectProjectDialog(self, evt):
        """ Select project event handler.

        :param evt: GUI Event.
        :type evt: Event

        """
        evt = evt
        try:
            if not self.current_session_id:
                try:
                    dlg = ProjectSelectDialog(self)
                    dlg.ShowModal()
                    dlg.Destroy()
                except Exception, e:
                    wos_logger.exception('SelectProjectDialog Exception: %s',
                                         str(e))
            else:
                msg = 'Cannot change project during session.'
                dlg = wx.MessageDialog(self, msg, 'Project selection error',
                                       wx.OK | wx.ICON_ERROR)
                dlg.ShowModal()
        except:
            wos_logger.exception('ShowSelectProjectDialog exception')

    def ShowPreferences(self, evt):
        """ Preferences dialog event handler

        :param evt: GUI Event.
        :type evt: Event.

        """
        evt = evt
        try:
            dlg = PreferencesDialog(self.config, self.list)
            dlg.ShowModal()
            dlg.Destroy()
            try:
                if (self.swnp.node.screens != self.config['SCREENS'] or
                        self.swnp.node.name != self.config['NAME']):
                    self.swnp.set_screens(int(self.config['SCREENS']))
                    self.swnp.node.name = self.config['NAME']
                    pub.sendMessage("update_screens", update=True)
            except:
                pass
        except:
            wos_logger.exception("showprefs exception")

    def LoadConfig(self):
        """ Loads a config file or creates one """
        if not os.path.exists(diwavars.CONFIG_PATH):
            self.CreateConfig()
        return configobj.ConfigObj(diwavars.CONFIG_PATH)

    def CreateConfig(self):
        """ Creates a config file """
        if not os.path.exists(diwavars.CONFIG_PATH):
            try:
                os.makedirs(os.path.dirname(diwavars.CONFIG_PATH))
            except:
                pass
            shutil.copy('config.ini', diwavars.CONFIG_PATH)

    def GetIcon(self, icon):
        """Fetches gui icons.

        :param icon: The icon file name.
        :type icon: String
        :rtype: :class:`wx.Image`

        """
        return wx.Image('icons/' + icon + '.png',
                        wx.BITMAP_TYPE_PNG).ConvertToBitmap()

    def SwnpSend(self, node, message):
        """Sends a message to the node.

        :param node: The node for which to send a message.
        :type node: String.
        :param message: The message.
        :type message: String.

        """
        try:
            self.swnp.send(node, 'MSG', message)
        except:
            wos_logger.exception("SwnpSend exception %s to %s" %
                                 (message, node))

    def InitUI(self):
        """ UI initing """
        self.EXITED = False
        wos_logger.debug('call savescreen!')
        img_path = os.path.join(r'\\' + diwavars.STORAGE, 'SCREEN_IMAGES',
                                self.swnp.node.id + '.png')
        filesystem.SaveScreen((diwavars.WINDOWS_MAJOR, diwavars.WINDOWS_MINOR),
                              img_path)
        self.screens = wx.BoxSizer(wx.HORIZONTAL)
        self.InitScreens()
        # Subscribe handlers
        pub.subscribe(self.UpdateScreens, "update_screens")
        pub.subscribe(self.MessageHandler, "message_received")
        #create UI
        try:
            vbox = wx.BoxSizer(wx.VERTICAL)
            btnsizer = wx.BoxSizer(wx.HORIZONTAL)

            self.pro_label = wx.TextCtrl(self.panel, -1, "No Project Selected",
                                         style=wx.TE_READONLY | wx.TE_CENTRE)
            # self.pro_label = wx.StaticText(self.panel, -1,
            #                                "No Project Selected")
            self.pro_label.SetBackgroundColour(wx.Colour(2, 235, 255))
            btnsizer.Add(self.pro_label, 1, wx.EXPAND)
            self.probtn = buttons.GenBitmapButton(self.panel, wx.ID_ANY,
                                                  self.GetIcon('button1'),
                                                  size=(-1, 32),
                                                  style=wx.NO_BORDER)
                                                # ,style=wx.BU_LEFT
            self.probtn.SetBackgroundColour(self.panel.GetBackgroundColour())
            self.probtn.focusClr = self.panel.GetBackgroundColour()
            self.probtn.shadowPenClr = self.panel.GetBackgroundColour()
            self.probtn.highlightPenClr = self.panel.GetBackgroundColour()
            self.probtn.faceDnClr = self.panel.GetBackgroundColour()
            self.probtn.SetToolTip(wx.ToolTip("Select a project"))
            self.probtn.Bind(wx.EVT_BUTTON, self.SelectProjectDialog)
            btnsizer.Add(self.probtn, 0)
            self.dirbtn = buttons.GenBitmapButton(self.panel, wx.ID_ANY,
                                                  self.GetIcon('folder'),
                                                  size=(-1, 32),
                                                  style=wx.NO_BORDER)
            self.dirbtn.SetBackgroundColour(self.panel.GetBackgroundColour())
            self.dirbtn.focusClr = self.panel.GetBackgroundColour()
            self.dirbtn.shadowPenClr = self.panel.GetBackgroundColour()
            self.dirbtn.highlightPenClr = self.panel.GetBackgroundColour()
            self.dirbtn.faceDnClr = self.panel.GetBackgroundColour()
            self.dirbtn.SetToolTip(wx.ToolTip("Open Project Directory"))
            self.dirbtn.Bind(wx.EVT_BUTTON, self.OpenProjectDir)
            self.dirbtn.Disable()
            btnsizer.Add(self.dirbtn, 0)
            self.sesbtn = buttons.GenBitmapButton(self.panel, wx.ID_ANY,
                                                  self.GetIcon('session_off'),
                                                  size=(-1, 32))
            self.sesbtn.SetBackgroundColour(self.panel.GetBackgroundColour())
            self.sesbtn.focusClr = self.panel.GetBackgroundColour()
            self.sesbtn.shadowPenClr = self.panel.GetBackgroundColour()
            self.sesbtn.highlightPenClr = self.panel.GetBackgroundColour()
            self.sesbtn.faceDnClr = self.panel.GetBackgroundColour()
            self.sesbtn.Bind(wx.EVT_BUTTON, self.OnSession)
            self.sesbtn.SetToolTip(wx.ToolTip("Toggle Session"))
            self.sesbtn.Disable()
            btnsizer.Add(self.sesbtn, 0, wx.LEFT | wx.RIGHT, 10)
            self.setbtn = buttons.GenBitmapButton(self.panel, wx.ID_ANY,
                                                  self.GetIcon('settings'),
                                                  size=(-1, 32))
            #self.setbtn.SetBitmap(self.GetIcon('settings'))
            self.setbtn.SetBackgroundColour(self.panel.GetBackgroundColour())
            self.setbtn.focusClr = self.panel.GetBackgroundColour()
            self.setbtn.shadowPenClr = self.panel.GetBackgroundColour()
            self.setbtn.highlightPenClr = self.panel.GetBackgroundColour()
            self.setbtn.faceDnClr = self.panel.GetBackgroundColour()
            self.setbtn.SetToolTip(wx.ToolTip("Settings"))
            self.setbtn.Bind(wx.EVT_BUTTON, self.ShowPreferences)
            btnsizer.Add(self.setbtn, 0, wx.LEFT | wx.RIGHT, 1)
            self.hidebtn = buttons.GenBitmapButton(self.panel, wx.ID_ANY,
                                                   self.GetIcon('minimize'),
                                                   size=(32, 32),
                                                   style=wx.NO_BORDER)
            self.hidebtn.SetBackgroundColour(self.panel.GetBackgroundColour())
            self.hidebtn.focusClr = self.panel.GetBackgroundColour()
            self.hidebtn.shadowPenClr = self.panel.GetBackgroundColour()
            self.hidebtn.highlightPenClr = self.panel.GetBackgroundColour()
            self.hidebtn.faceDnClr = self.panel.GetBackgroundColour()
            self.hidebtn.SetToolTip(wx.ToolTip("Minimize"))
            self.hidebtn.Bind(wx.EVT_BUTTON, self.OnTaskBarActivate)
            btnsizer.Add(self.hidebtn, 0, wx.LEFT, 1)
            self.closebtn = buttons.GenBitmapButton(self.panel, wx.ID_ANY,
                                                    self.GetIcon('close'),
                                                    size=(32, 32),
                                                    style=wx.NO_BORDER)
            self.closebtn.SetBackgroundColour(self.panel.GetBackgroundColour())
            self.closebtn.focusClr = self.panel.GetBackgroundColour()
            self.closebtn.shadowPenClr = self.panel.GetBackgroundColour()
            self.closebtn.highlightPenClr = self.panel.GetBackgroundColour()
            self.closebtn.faceDnClr = self.panel.GetBackgroundColour()
            self.closebtn.SetToolTip(wx.ToolTip("Exit"))
            self.closebtn.Bind(wx.EVT_BUTTON, self.OnExit)
            btnsizer.Add(self.closebtn, 0, wx.RIGHT, 1)
        except:
            wos_logger.exception("ui exception")
        vbox.Add(btnsizer, 0, wx.EXPAND | wx.BOTTOM, 3)

        screenSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.left = buttons.GenBitmapButton(self.panel, wx.ID_BACKWARD,
                                            self.GetIcon('left_arrow'),
                                            style=wx.NO_BORDER)
        self.left.SetBackgroundColour(self.panel.GetBackgroundColour())
        self.left.focusClr = self.panel.GetBackgroundColour()
        self.left.shadowPenClr = self.panel.GetBackgroundColour()
        self.left.highlightPenClr = self.panel.GetBackgroundColour()
        self.left.faceDnClr = self.panel.GetBackgroundColour()
        xflags = wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL | wx.RIGHT
        screenSizer.Add(self.left, 0, xflags, 2)
        screenSizer.Add(self.screens, 0, wx.EXPAND, 0)
        self.right = buttons.GenBitmapButton(self.panel, wx.ID_FORWARD,
                                             self.GetIcon('right_arrow'),
                                             style=wx.NO_BORDER)
        self.right.SetBackgroundColour(self.panel.GetBackgroundColour())
        self.right.focusClr = self.panel.GetBackgroundColour()
        self.right.shadowPenClr = self.panel.GetBackgroundColour()
        self.right.highlightPenClr = self.panel.GetBackgroundColour()
        self.right.faceDnClr = self.panel.GetBackgroundColour()
        screenSizer.Add(self.right, 0, xflags, 2)

        self.evtbtn = buttons.GenBitmapButton(self.panel, wx.ID_ANY,
                                              self.GetIcon('action'),
                                              size=(75, 75),
                                              style=wx.NO_BORDER)
        self.evtbtn.SetBackgroundColour(self.panel.GetBackgroundColour())
        self.evtbtn.focusClr = self.panel.GetBackgroundColour()
        self.evtbtn.shadowPenClr = self.panel.GetBackgroundColour()
        self.evtbtn.highlightPenClr = self.panel.GetBackgroundColour()
        self.evtbtn.faceDnClr = self.panel.GetBackgroundColour()
        self.evtbtn.SetToolTip(wx.ToolTip("Create Event"))
        self.evtbtn.Disable()
        self.evtbtn.Bind(wx.EVT_BUTTON, self.OnEvtBtn)
        # List for choices
        self.list = EventList(self)
        # Setting Bottom Banner
        self.banner_panel = wx.Panel(self,
                                     pos=(0, diwavars.FRAME_SIZE[1] - 50),
                                     size=(diwavars.FRAME_SIZE[0], 50))
        self.banner_panel.SetBackgroundColour(wx.Colour(45, 137, 255))
        self.logo = wx.StaticBitmap(self.banner_panel, id=wx.ID_ANY,
                                    bitmap=self.GetIcon('logo'), pos=(5, 0))
        self.logo.Bind(wx.EVT_LEFT_DOWN, self.OnAboutBox)
        self.diwawabtn = buttons.GenBitmapButton(self.banner_panel, wx.ID_ANY,
                                                 self.GetIcon('diwawa'),
                                                 style=wx.NO_BORDER,
                                                 pos=(90, 4),
                                                 size=(118, 30))
        self.diwawabtn.focusClr = wx.Colour(45, 137, 255)
        self.diwawabtn.shadowPenClr = wx.Colour(45, 137, 255)
        self.diwawabtn.highlightPenClr = wx.Colour(45, 137, 255)
        self.diwawabtn.faceDnClr = wx.Colour(45, 137, 255)
        self.diwawabtn.Bind(wx.EVT_BUTTON, self.OnWABtn)
        self.diwawabtn.SetToolTip(wx.ToolTip("Web Application"))
        self.diwambbtn = buttons.GenBitmapButton(self.banner_panel, wx.ID_ANY,
                                                 self.GetIcon('diwamb'),
                                                 style=wx.BORDER_NONE,
                                                 pos=(203, 4), size=(113, 32))
        self.diwambbtn.SetBackgroundColour(wx.Colour(45, 137, 255))
        self.diwambbtn.focusClr = wx.Colour(45, 137, 255)
        self.diwambbtn.shadowPenClr = wx.Colour(45, 137, 255)
        self.diwambbtn.highlightPenClr = wx.Colour(45, 137, 255)
        self.diwambbtn.faceDnClr = wx.Colour(45, 137, 255)
        self.diwambbtn.Bind(wx.EVT_BUTTON, self.OnMBBtn)
        self.diwambbtn.SetToolTip(wx.ToolTip("Meeting Browser"))
        self.status_text = wx.StaticText(self.banner_panel, -1, '',
                                         pos=(diwavars.FRAME_SIZE[0] - 220, 0))
        self.banner = wx.StaticBitmap(self.banner_panel, id=wx.ID_ANY,
                                      bitmap=self.GetIcon('balls'),
                                      pos=(diwavars.FRAME_SIZE[0] - 250, 0))
        # self.statusbg = wx.StaticBitmap(self.banner_panel, id=wx.ID_ANY,
        #                                bitmap=self.GetIcon('statusbg'),
        #                                pos=(diwavars.FRAME_SIZE[0] - 150, 0),
        #                                size=(150,50))
        self.infobtn = buttons.GenBitmapButton(self.banner, wx.ID_ANY,
                                               self.GetIcon('info'),
                                               style=wx.BORDER_NONE,
                                               pos=(80, 5), size=(20, 20))
        self.infobtn.SetBackgroundColour(wx.Colour(45, 137, 255))
        self.infobtn.focusClr = wx.Colour(45, 137, 255)
        self.infobtn.shadowPenClr = wx.Colour(45, 137, 255)
        self.infobtn.highlightPenClr = wx.Colour(45, 137, 255)
        self.infobtn.faceDnClr = wx.Colour(45, 137, 255)
        self.infobtn.Bind(wx.EVT_BUTTON, self.OnInfoBtn)
        self.infobtn.SetToolTip(wx.ToolTip("Info"))
        msg = ' '.join(["DiWaCS", diwavars.VERSION])
        version = wx.StaticText(self.banner_panel, -1, msg, pos=(5, 35),
                                style=wx.ALIGN_CENTRE)
        version.SetFont(wx.Font(6, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL,
                                wx.FONTWEIGHT_LIGHT))
        screenSizer.Add(self.evtbtn, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 30)
        self.left.Bind(wx.EVT_BUTTON, self.Shift)
        self.right.Bind(wx.EVT_BUTTON, self.Shift)
        vbox.Add(screenSizer, 0)
        self.hidden = 0
        self.SetSizer(vbox)
        pub.sendMessage("update_screens", update=True)

    def OnWABtn(self, unused_event):
        webbrowser.open("http://" + diwavars.STORAGE + "/")

    def OnMBBtn(self, unused_event):
        webbrowser.open("http://" + diwavars.STORAGE + "/mb/")

    def OnInfoBtn(self, unused_event):
        webbrowser.open("http://" + diwavars.STORAGE + "/help/")

    def GetNodeByName(self, name):
        for node in self.nodes:
            if node[2] == name:
                return node[0]
        return None

    def ClearStatusText(self):
        self.status_text.SetLabel("")

    def OnEvtBtn(self, evt):
        """ Event Button handler.

        :param evt: GUI Event.
        :type evt: Event.

        """
        #create default event
        evt.Skip()
        self.list.SetFocus()
        self.list.ShowNow()

    def CustomEventMenu(self, event):
        event.Skip()
        title = self.event_menu_title_by_id[event.GetId()]
        if not self.is_responsive:
            self.SwnpSend(self.responsive, "event;" + title)
        elif self.current_project_id and self.current_session_id:
            wx.CallAfter(diwavars.WINDOW_TAIL * 1000, self.worker.CreateEvent,
                         title)

    def Shift(self, evt):
        """ Caroussel Shift function.

        :param evt: GUI Event.
        :type evt: Event.

        """
        evt.Skip()
        if len(self.nodes) > 3:
            if evt.GetId() == wx.ID_BACKWARD:
                if self.iterator > 0:
                    self.iterator = self.iterator - 1
            elif evt.GetId() == wx.ID_FORWARD:
                if self.iterator < len(self.nodes) - 3:
                    self.iterator = self.iterator + 1
            pub.sendMessage("update_screens", update=True)

    def SetScanObserver(self):
        """ Observer for created files in scanned or taken with camera. """
        try:
            wos_logger.debug("Setting scan observer")
            if self.scan_observer:
                try:
                        self.scan_observer.stop()
                        del self.scan_observer
                except NameError:
                    pass
            self.scan_observer = Observer()
            path = r'\\' + diwavars.STORAGE + r'\Pictures'
            if diwavars.DEBUG:
                path = r'C:\Scan'
            shandler = controller.SCAN_HANDLER(self.current_project_id)
            self.scan_observer.schedule(shandler, path=path, recursive=True)
            self.scan_observer.start()
            self.is_responsive = True
            # self.swnp.node.data = 'responsive'
        except Exception, e:
            self.is_responsive = False
            # self.swnp.node.data = ''
            wos_logger.exception("error setting scan observer:%s", str(e))

    def SetProjectObserver(self):
        """ Observer for filechanges in project dir """
        try:
            cpid = self.current_project_id
            if cpid:
                try:
                    if self.project_folder_observer:
                        self.project_folder_observer.stop()
                        del self.project_folder_observer
                except NameError:
                    pass
                self.project_folder_observer = Observer()
                pfevthandler = controller.PROJECT_FILE_EVENT_HANDLER(cpid)
                ppath = controller.GetProjectPath(cpid)
                self.project_folder_observer.schedule(pfevthandler, path=ppath,
                                                      recursive=True)
                self.project_folder_observer.start()
            self.is_responsive = True
            self.swnp.node.data = 'responsive'
        except Exception, e:
            self.is_responsive = False
            self.swnp.node.data = ''
            wos_logger.exception("error setting PROJECT observer:%s", str(e))

    def OnProjectSelected(self):
        """ Project selected event handler """
        controller.InitSyncProjectDir(self.current_project_id)
        self.activity = controller.AddActivity(self.current_project_id,
                                               diwavars.PGM_GROUP,
                                               self.current_session_id,
                                               self.activity)
        self.SwnpSend('SYS', 'current_activity;' + str(self.activity))

    def GetRandomResponsive(self):
        has_nodes = False
        if len(self.nodes) > 1:
            for node in self.swnp.get_list():
                if node < 10:
                    has_nodes = True
                    break
        if not has_nodes:
            self.SetResponsive()
            return
        item = '255'
        self.is_responsive = False
        self.swnp.node.data = ''
        while int(item) > 10:
            try:
                item = self.rand.choice(self.swnp.get_screen_list())
            except IndexError:
                wos_logger.debug('get_random error: nodes empty')
                return
        wos_logger.debug('Random responsive is %s', item)
        self.SwnpSend(item, 'set;responsive')

    def PaintSelect(self, evt):
        """Paints the selection of a node.

        .. note:: For future use.

        :param evt: GUI Event
        :type evt: Event.

        """
        dc = wx.ClientDC(self.panel)
        dc.Clear()
        if self.screen_selected == evt.GetId():
            self.screen_selected = None
        elif True:  # (evt.GetId())<len(self.nodes):
            self.screen_selected = self.iterator + evt.GetId()
            dc.BeginDrawing()
            pen = wx.Pen('#4c4c4c', 3, wx.SOLID)
            dc.SetPen(pen)
            dc.DrawLine(66 + self.screen_selected * (6 + 128), 110,
                        98 + self.screen_selected * (6 + 128), 110)
            dc.EndDrawing()

    def SelectNode(self, evt):
        """Handles the selection of a node, start remote control.

        .. note:: For future use.

        :param evt: GUI Event
        :type evt: Event.

        """
        global MOUSE_X, MOUSE_Y, CAPTURE
        index = self.iterator + evt.GetId()
        id_ = self.nodes[(index) % len(self.nodes)][0]
        if evt.GetId() >= len(self.nodes) or id_ == self.swnp.id:
            if CONTROLLED and id_ == self.swnp.id:
                self.SwnpSend(self.swnp.id, 'remote_end;now')
                self.SwnpSend(str(CONTROLLED), 'remote_end;now')
            return
        if id_ in self.selected_nodes:
            # End Remote
            self.selected_nodes.remove(id_)
            CAPTURE = False
            self.capture_thread.unhook()
            self.overlay.Hide()
        else:
            # Start remote
            CAPTURE = True
            self.capture_thread.ResetMouseEvents()
            self.capture_thread.hook()
            self.SwnpSend(id_, 'remote_start;%s' % self.swnp.id)
            MOUSE_X, MOUSE_Y = evt.GetPositionTuple()
            self.selected_nodes.append(id_)
            self.Refresh()
            self.overlay.Show()

    def InitScreens(self):
        """ Inits Screens """
        wos_logger.debug("init screens start")
        i = 0
        self.selected_nodes = []
        try:
            while i < diwavars.MAX_SCREENS:
                s = wx.BoxSizer(wx.VERTICAL)
                tra = wx.Image(diwavars.NO_SCREEN, wx.BITMAP_TYPE_PNG)
                tra = tra.ConvertToBitmap()
                img = wx.StaticBitmap(parent=self.panel, id=i, bitmap=tra)
                img.Bind(wx.EVT_LEFT_DOWN, self.SelectNode)
                self.imgs.insert(i, img)
                dt = DropTarget(img, self, i)
                img.SetDropTarget(dt)
                self.filedrops.insert(i, dt)
                s.Add(img)
                self.screens.Add(s, 0, wx.LEFT | wx.RIGHT, border=3)
                i += 1
        except:
            wos_logger.exception("init screens except")
        self.Layout()
        self.Refresh()
        self.init_screens_done = True

    def AlignCenterTop(self):
        """Aligns frame to Horizontal center and vertical top"""
        dw = wx.DisplaySize()[0]
        w = self.GetSize()[0]
        x = (dw - w) / 2
        self.SetPosition((x, 0))

    def HideScreens(self):
        """ Hides all screens """
        self.right.SetBitmapLabel(self.GetIcon('0'))
        self.left.SetBitmapLabel(self.GetIcon('0'))
        for i in self.imgs:
            temp = wx.Image(diwavars.NO_SCREEN, wx.BITMAP_TYPE_PNG)
            i.SetBitmap(temp.ConvertToBitmap())
            i.SetToolTip(None)

    def UpdateScreens(self, update):
        """Called when screens need to be updated and redrawn

        :param update: Pubsub needs one param, therefore it is called update.
        :type update: Boolean

        """
        update = update  # Intentionally left unused.
        if not self.init_screens_done:
            return
        self.HideScreens()
        self.nodes = []
        for node in self.swnp.get_screen_list():
            self.nodes.append((node.id, node.screens, node.name))
            self.worker.AddRegEntry(node.name, node.id)
        if len(self.nodes):
            if len(self.nodes) > 3:
                self.left.SetBitmapLabel(self.GetIcon('left_arrow'))
                self.right.SetBitmapLabel(self.GetIcon('right_arrow'))
            i = 0
            while i < diwavars.MAX_SCREENS and i < len(self.nodes):
                xi = (i + self.iterator) % len(self.nodes)
                try:
                    img_path = filesystem.GetNodeImg(self.nodes[xi][0])
                    try:
                        bm = wx.Image(img_path,
                                      wx.BITMAP_TYPE_ANY).ConvertToBitmap()
                    except:
                        bm = wx.Image(diwavars.DEFAULT_SCREEN,
                                      wx.BITMAP_TYPE_ANY).ConvertToBitmap()
                    img = self.imgs[i]
                    img.SetBitmap(bm)
                    img.SetToolTip(wx.ToolTip(self.nodes[xi][2]))
                    i += 1
                except:
                    msg = str(self.nodes[xi])
                    wos_logger.exception("nodes update except: " + msg)
        self.worker.CheckResponsive()
        self.Refresh()

    def OnExit(self, event):
        """ Exits program.

        :param event: GUI Event
        :type event: Event.

        """
        if not self.EXITED:
            try:
                self.EXITED = True
                self.overlay.Destroy()
                self.Hide()
                self.trayicon.RemoveIcon()
                self.trayicon.Destroy()
                self.closebtn.SetToolTip(None)
                if not event == 'conn_err' and self.is_responsive:
                    wos_logger.debug("On exit self is responsive")
                    self.RemoveObservers()
                    controller.EndSession(self.current_session_id)
                    controller.UnsetActivity(diwavars.PGM_GROUP)
                if not event == 'conn_err' and controller.LastActiveComputer():
                    wos_logger.debug("On exit self is last active comp.")
                    controller.UnsetActivity(diwavars.PGM_GROUP)
                    if self.current_session_id:
                        controller.EndSession(self.current_session_id)
                utils.MapNetworkShare('W:')
                diwavars.UpdateResponsive(0)
                sleep(5)
                self.cmfh.stop()
                self.worker.RemoveAllRegEntries()
                #self.swnp.close()
                self.Destroy()
                wos_logger.info('Application closed')
                sys.exit(0)
            except CloseError, e:
                raise e
            except Exception, e:
                wos_logger.exception('Exception in Close:' + str(e))
                for thread in threading.enumerate():
                    wos_logger.debug(thread.getName())
                self.Destroy()
                sys.exit(0)

    def OnAboutBox(self, unused_event):
        """ About dialog.

        :param e: GUI Event.
        :type e: Event.

        """
        description = diwavars.APPLICATION_NAME + " is the windows client for"\
            " DiWa - A distributed meeting room collaboration system.\n\n"\
            "Lead programmer: Nick Eriksson\n"\
            "Contributors: Mika P. Nieminen, Mikael Runonen, Mari Tyllinen, "\
            "Vikki du Preez, Marko Nieminen\n\n"

        unused_licence = """
        DiwaCS is free software.
        """
        info = wx.AboutDialogInfo()

        info.SetIcon(wx.Icon(os.path.join("data", "splashscreen.png"),
                             wx.BITMAP_TYPE_PNG))
        info.SetName(diwavars.APPLICATION_NAME)
        info.SetVersion(diwavars.VERSION)
        info.SetDescription(description)
        info.SetCopyright('(c) 2012-2013 DiWa project by Strategic Usability'\
                          ' Research Group STRATUS, Aalto University School'\
                          ' of Science.')
        info.SetWebSite('http://stratus.soberit.hut.fi/')
        wx.AboutBox(info)

    def OnIconify(self, unused_event):
        """ Window minimize event handler

        :param evt: GUI Event.
        :type evt: Event.

        """
        if self.IsIconized():
            self.Show()
            self.Raise()
            self.Iconize(False)
        else:
            self.Iconize(True)
            self.Hide()

    def OnTaskBarActivate(self, evt):
        """ Taskbar activate event handler.

        :param evt: GUI Event.
        :type evt: Event.

        """
        evt.Skip()
        if self.IsIconized():
            self.Show()
            self.Raise()
            self.Iconize(False)
        else:
            self.Iconize(True)
            self.Hide()

    def OnTaskBarClose(self, unused_event):
        """ Taskbar close event handler.

        :param evt: GUI Event.
        :type evt: Event.

        """
        wx.CallAfter(self.Close)

    def MessageHandler(self, message):
        """Message handler for received messages

        :param message: Received message.
        :type message: an instance of :class:`swnp.Message`

        """
        global CONTROLLED, CONTROLLING
        try:
            if diwavars.DEBUG:
                    wos_logger.debug('ZMQ PUBSUB Message:' + message)
            cmd, target = message.split(';')
            if cmd == 'open':
                """Open all files in list"""
                target = eval(target)
                for f in target:
                    if self.current_session_id:
                        controller.CreateFileaction(f, 6,
                                                    self.current_session_id,
                                                    self.current_project_id)
                    filesystem.OpenFile(f)
            if cmd == 'new_responsive':
                if self.is_responsive:
                    self.StopResponsive()
                    self.is_responsive = False
                    self.responsive = target
            if cmd == 'event':
                if self.is_responsive or diwavars.DEBUG:
                    self.worker.CreateEvent(target)
            if cmd == 'key':
                e, key, scan = target.split(',')
                e = int(e)
                flags = 0
                if e == 257:
                    flags = 2
                macro.send_input('k', int(key), flags, int(scan))
            if cmd == 'remote_start':
                CONTROLLED = target
            if cmd == 'remote_end':
                if CONTROLLED:
                    #release alt
                    macro.send_input('k', 18, 2, 56)
                if CONTROLLING:
                    global CAPTURE
                    self.SetCursor(DEFAULT_CURSOR)
                    del self.selected_nodes[:]
                    CAPTURE = False
                    self.capture_thread.unhook()
                    self.overlay.Hide()
                CONTROLLED = False
                CONTROLLING = False
            if cmd == 'mouse_move':
                x, y = target.split(',')
                macro.send_input('m', [int(x), int(y)], 0x0001)
            if cmd == 'mouse_event':
                target, wheel = target.split(',')
                flags = 0
                mouseData = 0
                if int(target) == 0x201:
                    flags = 0x0002
                elif int(target) == 0x202:
                    flags = 0x0004
                elif int(target) == 0x204:
                    flags = 0x0008
                elif int(target) == 0x205:
                    flags = 0x0010
                elif int(target) == 0x207:
                    flags = 0x0020
                elif int(target) == 0x208:
                    flags = 0x0040
                elif int(target) == 0x20A:
                    flags = 0x0800
                    mouseData = int(wheel) * 120
                elif int(target) == 0x20E:
                    flags = 0x01000
                    mouseData = int(wheel) * 120
                macro.send_input('m', [0, 0], flags, scan=0,
                                 mouseData=mouseData)
            if cmd == 'url':
                webbrowser.open(target)
            if cmd == 'set' and target == 'responsive':
                if not diwavars.RESPONSIVE == 0:
                    self.SetResponsive()
                    self.is_responsive = True
            if cmd == 'screenshot':
                if self.swnp.node.screens > 0:
                    filesystem.ScreenCapture(
                        controller.GetProjectPath(self.current_project_id),
                        self.swnp.node.id)
            if cmd == 'current_session':
                target = int(target)
                if self.current_session_id != target:
                    self.SetCurrentSession(target)
            if cmd == 'current_project':
                if self.current_project_id != target:
                    target = int(target)
                if self.current_project_id != target:
                    self.SetCurrentProject(target)
            if cmd == 'current_activity':
                if self.activity != target:
                    self.activity = target
                self.SetCurrentProject(
                    controller.GetProjectIdByActivity(self.activity)
                )
                self.SetCurrentSession(
                    controller.GetSessionIdByActivity(self.activity)
                )

        except Exception:
            wos_logger.exception('Exception in MessageHandler:')


if __name__ == '__main__':
    wos_logger.info("\n\n\n")
    wos_logger.info('Application started')
    #version_checker = CHECK_UPDATE().start()
    app = wx.App()
    w = GUI(parent=None, title=(diwavars.APPLICATION_NAME + ' ' +
                                diwavars.VERSION))
    app.MainLoop()
