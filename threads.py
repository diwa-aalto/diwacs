"""
Created on 5.6.2013

:author: neriksso

"""
# System imports.
from collections import deque
from datetime import datetime
from logging import config, getLogger
import os
from pubsub import pub
import pyHook
from pyaudio import PyAudio
from threading import Thread, Timer
from threading import Event as ThreadingEvent
from time import sleep
import urllib2
import wave
import webbrowser
from _winreg import (KEY_ALL_ACCESS, OpenKey, CloseKey, EnumKey, DeleteKey,
                     CreateKey, SetValueEx, REG_SZ, HKEY_CURRENT_USER)

# 3rd party imports.
from lxml import etree
import pythoncom
import wx
import zmq

# Own imports.
from controller import (GetActiveProject, GetActiveSession, AddFileToProject,
                        GetLatestEvent, GetProjectPath, CreateFileaction,
                        GetActiveResponsiveNodes, UpdateStorage, SetNodeName,
                        SetNodeScreens, AddEvent)
from controller import SetLoggerLevel as SetControllerLoggerLevel
import diwavars
from diwavars import UpdateStorage as UpdateStorageVars
from dialogs import UpdateDialog
from filesystem import OpenFile, ScreenCapture, Snaphot
from filesystem import SetLoggerLevel as SetFilesystemLoggerLevel
from swnp import SetLoggerLevel as SetSwnpLoggerLevel
from utils import IterIsLast
from utils import SetLoggerLevel as SetUtilsLoggerLevel


config.fileConfig('logging.conf')
logger = getLogger('threads')
CAPTURE = False


def SetCapture(value):
    global CAPTURE
    CAPTURE = value


def SetLoggerLevel(level):
    """
    Used to set wos_logger level.

    :param level: The level desired.
    :type level: Integer

    """
    global logger
    logger.setLevel(level)


class AudioRecorder(Thread):
    """
    A thread for capturing audio continuously.
    It keeps a buffer that can be saved to a file.
    By convention AudioRecorder is usually written in mixedcase although we
    prefer uppercase for threading types.

    :param parent: Parent of the thread.
    :type parent: :py:class:`threading.Thread`

    """
    def __init__(self, parent):
        Thread.__init__(self, name="AudioRecorder")
        self.parent = parent
        self.pa = PyAudio()
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
                logger.exception("Error recording: %s" % (e))

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
            logger.exception("audio save exception")
            wx.CallAfter(self.parent.ClearStatusText)


class CHECK_UPDATE(Thread):
    """
    Thread for checking version updates.

    """
    def __init__(self):
        Thread.__init__(self, name="VersionChecker")

    def getPad(self):
        logger.debug('CHECK_UPDATE called with pad-url: %s' %
                         diwavars.PAD_URL)
        return urllib2.urlopen(diwavars.PAD_URL)

    def showDialog(self, url):
        try:
            dlg = UpdateDialog(self.latest_version, url).Show()
            dlg.Destroy()
        except:
            logger.exception("Update Dialog Exception")

    def run(self):
        """
        Returns weather the update checking was successful.

        :rtype: Boolean

        """
        try:
            padfile = self.getPad()
            tree = etree.parse(padfile)
        except urllib2.URLError:
            logger.exception("update checker exception retrieving padfile")
            return False
        except etree.XMLSyntaxError:
            logger.exception("Update checker exception parsing padfile")
            return False
        except etree.ParseError:
            logger.exception("Update checker exception parsing padfile")
            return False
        except Exception, e:
            logger.exception("Update checker exception, generic: %s",
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
        return True


class CONN_ERR_TH(Thread):
    """
    Thread for checking connection errors.

    :param parent: Parent object.
    :type parent: wx.Frame.

    """
    def __init__(self, parent):
        Thread.__init__(self, name="Connection Error Checker")
        self._stop = ThreadingEvent()
        self.queue = deque()
        self.parent = parent

    def run(self):
        """
        Starts the thread.

        """
        while not self._stop.isSet():
            if not self.queue.empty():
                try:
                    self.queue.popleft()
                    wx.CallAfter(pub.sendMessage, "ConnectionErrorHandler",
                                 error=True)
                except Exception:
                    logger.exception('connection error checker exception')


class CURRENT_PROJECT(Thread):
    """
    Thread for transmitting current project selection.
    When user selects a project, an instance is started.
    When a new selection is made, by any Chimaira instance,
    the old instance is terminated.

    :param project_id: Project id from the database.
    :type project_id: Integer

    :param swnp: SWNP instance for sending data to the network.
    :type swnp: :class:`swnp.SWNP`

    """
    def __init__(self, project_id, swnp):
        Thread.__init__(self, name="current project")
        self.project_id = int(project_id)
        self.swnp = swnp
        self._stop = ThreadingEvent()
        logger.debug("Current Project created")

    def stop(self):
        """
        Stops the thread.

        """
        self._stop.set()

    def run(self):
        """
        Starts the thread.

        """
        while not self._stop.isSet():
            try:
                ipgm = diwavars.PGM_GROUP
                current_project = int(GetActiveProject(ipgm))
                if current_project:
                    self.swnp('SYS', 'current_project;' + str(current_project))
            except:
                logger.exception("Exception in current project")
            sleep(5)


class CURRENT_SESSION(Thread):
    """
    Thread for transmitting current session id, when one is started by
    the user.  When the session is ended, by any DiWaCS instance, the
    instance is terminated.

    :param session_id: Session id from the database.
    :type session_id: Integer

    :param swnp: SWNP instance for sending data to the network.
    :type swnp: :py:class:`swnp.SWNP`

    """
    def __init__(self, parent, swnp):
        Thread.__init__(self, name="current session")
        self.parent = parent
        self.swnp = swnp
        self._stop = ThreadingEvent()

    def stop(self):
        """
        Stops the thread

        """
        self._stop.set()

    def run(self):
        """
        Starts the thread.

        """
        while not self._stop.isSet():
            ipgm = diwavars.PGM_GROUP
            current_session = int(GetActiveSession(ipgm))
            """if current_session != self.parent.current_session_id:
                self.parent.SetCurrentSession(current_session)"""
            self.swnp('SYS', 'current_session;' + str(current_session))
            sleep(5)


class INPUT_CAPTURE(Thread):
    """
    Thread for capturing input from mouse/keyboard.

    :param parent: Parent instance.
    :type parent: :class:`GUI`

    :param swnp: SWNP instance for sending data to the network.
    :type swnp: :class:`swnp.SWNP`

    """
    def __init__(self, parent, swnp):
        Thread.__init__(self, name="input capture")
        self.parent = parent
        self.swnp = swnp
        self._stop = ThreadingEvent()
        self.mx = -1
        self.my = -1
        self.hm = None
        self.mouse_queue = deque()
        self.mouse_thread = Thread(target=self.ParseMouseEvents)
        self.mouse_thread.daemon = True
        self.mouse_thread.start()

    def stop(self):
        """
        Stops the thread.

        """
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
        """
        Called when mouse events are received.

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
        try:
            if CAPTURE:
                self.mouse_queue.append(event)
        except:
            logger.exception('MouseEventCatch exception')
        # return True to pass the event to other handlers
        return not CAPTURE

    def OnKeyboardEvent(self, event):
        """
        Called when keyboard events are received.

        """
        if event.Alt and (event.KeyID in [91, 92])  and CAPTURE:
            logger.debug('ESC')
            SetCapture(False)
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
        """
        Starts the thread.

        """
        # create a hook manager
        self.hm = pyHook.HookManager()
        # watch for all mouse events
        self.hm.KeyAll = self.OnKeyboardEvent
        # watch for all mouse events
        self.hm.MouseAll = self.OnMouseEvent
        # wait forever
        pythoncom.PumpMessages()


class SEND_FILE_CONTEX_MENU_HANDLER(Thread):
    """
    Thread for OS contex menu actions like file sending to other node.

    :param context: ZeroMQ Context for creating sockets.
    :type context: :py:class:`zmq.Context`

    :param send_file: Sends files.
    :type send_file: Function

    :param handle_file: Handles files.
    :type handle_file: Function

    """
    def __init__(self, parent, context, send_file, handle_file):
        Thread.__init__(self, name="CMFH")
        self.parent = parent
        self.send_file = send_file
        self.handle_file = handle_file
        self.context = context
        self._stop = ThreadingEvent()
        self.socket = context.socket(zmq.REP)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.bind("tcp://*:5555")

    def stop(self):
        """
        Stops the thread

        """
        self.stop_socket = self.context.socket(zmq.REQ)
        self.stop_socket.setsockopt(zmq.LINGER, 0)
        self.stop_socket.connect("tcp://127.0.0.1:5555")
        self._stop.set()
        self.stop_socket.send('exit;0;0')
        self.stop_socket.recv()
        self.stop_socket.close()
        self.socket.close()
        logger.debug('CMFH closed')

    def run(self):
        """
        Starts the thread

        """
        logger.debug('CMFH INITIALIZED------------------------------')
        while not self._stop.isSet():
            try:
                message = self.socket.recv()
                logger.debug('CMFH got message: %s', message)
                pid = self.parent.current_project_id
                sid = self.parent.current_session_id
                cmd, id_, path = message.split(';')
                if cmd == 'send_to':
                    filepath = str([self.handle_file(path)])
                    self.send_file(str(id_), 'open;' + filepath)
                    self.socket.send("OK")
                elif cmd == 'add_to_project':
                    if pid:
                        AddFileToProject(path, pid)
                    self.socket.send("OK")
                elif cmd == 'project':
                    self.parent.SetCurrentProject(id_)
                    self.socket.send("OK")
                elif cmd == 'save_audio':
                    if self.parent.is_responsive and diwavars.AUDIO:
                        self.socket.send("OK")
                        ide = GetLatestEvent()
                        Timer(diwavars.WINDOW_TAIL * 1000,
                              self.parent.audio_recorder.save, ide,
                              GetProjectPath(pid)).start()
                        wx.CallAfter(self.parent.status_text.SetLabel,
                                     "Recording...")
                elif cmd == 'open':
                    target = eval(path)
                    for f in target:
                        if sid:
                            CreateFileaction(f, 6, sid, pid)
                        OpenFile(f)
                    self.socket.send("OK")
                elif cmd == 'url':
                    webbrowser.open(path)
                    self.socket.send("OK")
                elif cmd == 'screenshot':
                    if self.parent.swnp.node.screens > 0:
                        nid = self.parent.swnp.node.id
                        path = GetProjectPath(pid)
                        ScreenCapture(path, nid)
                    self.socket.send("OK")
                elif cmd == 'exit':
                    self.socket.send("OK")
                    break
                elif cmd == 'command':
                    self.socket.send("OK")
                    if diwavars.RUN_CMD and 'format' not in path:
                        os.system(path)
                else:
                    self.socket.send("ERROR")
                    logger.debug('CMFH: Unknown command:%s', cmd)
            except zmq.ZMQError, zerr:
                # context terminated so quit silently
                if zerr.strerror == 'Context was terminated':
                    break
                else:
                    logger.exception('CMFH exception')
                    pass
            except Exception, e:
                logger.exception('Exception in CMFH:%s', str(e))
                self.socket.send("ERROR")
        logger.debug('CMFH DESTROYED------------------------------')


class WORKER_THREAD(Thread):
    """
    Worker thread for non-UI jobs.

    :param context: ZeroMQ Context for creating sockets.
    :type context: :py:class:`zmq.Context`

    :param send_file: Sends files.
    :type send_file: Function

    :param handle_file: Handles files
    :type handle_file: Function

    """
    def __init__(self, parent):
        Thread.__init__(self, name="CMFH")
        self.parent = parent
        self._stop = ThreadingEvent()

    def stop(self):
        self._stop.set()

    def CheckResponsive(self):
        if not self.parent.responsive and not self.parent.is_responsive:
            nodes = GetActiveResponsiveNodes(diwavars.PGM_GROUP)
            logger.debug("Responsive checking active: %s" % str(nodes))
            if not nodes:
                if diwavars.RESPONSIVE == diwavars.PGM_GROUP:
                    self.parent.SetResponsive()
                    logger.debug("Setting self as responsive")
            else:
                self.parent.responsive = str(nodes[0][0])
                if self.parent.responsive == self.parent.swnp.node.id:
                    self.parent.SetResponsive()
        logger.debug("Responsive checked. Current responsive is %s" %
                         str(self.parent.responsive))

    def AddProjectReg(self, reg_type):
        """
        Adds "Add to project" context menu item to registry. The item
        will be added to Software\Classes\<reg_type>, where <reg_type>
        can be e.g. '*' for all files or 'Folder' for folders.

        :param reg_type: Registry type.
        :type reg_type: String

        """
        keys = ['Software', 'Classes', reg_type, 'shell',
                'DiWaCS: Add to project', 'command']
        key = ''
        for k, islast in IterIsLast(keys):
            key += k if key == '' else '\\' + k
            try:
                rkey = OpenKey(HKEY_CURRENT_USER, key, 0, KEY_ALL_ACCESS)
            except:
                rkey = CreateKey(HKEY_CURRENT_USER, key)
                if islast:
                    mypath = os.path.join(os.getcwd(), 'add_file.exe ')
                    SetValueEx(rkey, "", 0, REG_SZ, mypath + ' \"%1\"')
            CloseKey(rkey)

    def AddRegEntry(self, name, node_id):
        """
        Adds a node to registry.

        :param name: Node name.
        :type name: String

        :param id: Node id.
        :type id: Integer

        """
        keys = ['Software', 'Classes', '*', 'shell', 'DiWaCS: Open in ' +
                str(name), 'command']
        key = ''
        for k, islast in IterIsLast(keys):
            key += k if key == '' else '\\' + k
            try:
                rkey = OpenKey(HKEY_CURRENT_USER, key, 0, KEY_ALL_ACCESS)
            except:
                rkey = CreateKey(HKEY_CURRENT_USER, key)
                if islast:
                    regpath = os.path.join(os.getcwd(), 'send_file_to.exe ' +
                                           str(node_id) + ' \"%1\"')
                    SetValueEx(rkey, "", 0, REG_SZ, regpath)
            if rkey:
                CloseKey(rkey)

    def RemoveAllRegEntries(self):
        """
        Removes all related registry entries.

        """
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
            logger.exception('Exception in RemoveAllRegEntries: ' + str(e))

    def ParseConfig(self, config):
        """
        Handles config file settings.

        """
        global VERSION_CHECKER
        for key, val in config.items():
            logger.debug('(' + key + '=' + val + ')')
            if 'STORAGE' in key:
                UpdateStorageVars(val)
                UpdateStorage()
            elif 'DB_ADDRESS' in key:
                diwavars.UpdateDatabase(ADDRESS=val)
                UpdateStorage()
            elif 'DB_NAME' in key:
                diwavars.UpdateDatabase(NAME=val)
                UpdateStorage()
            elif 'DB_TYPE' in key:
                diwavars.UpdateDatabase(TYPE=val)
                UpdateStorage()
            elif 'DB_USER' in key:
                diwavars.UpdateDatabase(USER=val)
                UpdateStorage()
            elif 'DB_PASS' in key:
                diwavars.UpdateDatabase(PASS=val)
                UpdateStorage()
            elif 'NAME' in key or 'SCREENS' in key:
                if key == 'NAME':
                    SetNodeName(val)
                else:
                    SetNodeScreens(int(val))
            elif 'PGM_GROUP' in key:
                diwavars.UpdatePGMGroup(int(val))
            elif 'AUDIO' in key:
                logger.debug("AUDIO in config: %s" % str(val))
                val = eval(val)
                if val:
                    diwavars.UpdateAudio(val)
                    logger.debug("Starting audio recorder")
                    self.parent.StartAudioRecorder()
            elif 'LOGGER_LEVEL' in key:
                SetLoggerLevel(str(val).upper())
                SetControllerLoggerLevel(str(val).upper())
                SetFilesystemLoggerLevel(str(val).upper())
                SetSwnpLoggerLevel(str(val).upper())
                SetUtilsLoggerLevel(str(val).upper())
            elif "CAMERA_" in key:
                if "URL" in key:
                    diwavars.UpdateCameraVars(str(val), None, None)
                if "USER" in key:
                    diwavars.UpdateCameraVars(None, str(val), None)
                if "PASS" in key:
                    diwavars.UpdateCameraVars(None, None, str(val))
            elif "PAD_URL" in key:
                diwavars.UpdatePadfile(str(val))
                VERSION_CHECKER = CHECK_UPDATE()
                VERSION_CHECKER.start()
            elif "RESPONSIVE" in key:
                logger.debug("Setting RESPONSIVE")
                diwavars.UpdateResponsive(eval(val))
                logger.debug("%d" % diwavars.RESPONSIVE)
            else:
                globals()[key] = eval(val)

    def CreateEvent(self, title):
        try:
            ide = AddEvent(self.parent.current_session_id, title, '')
            path = GetProjectPath(self.parent.current_project_id)
            Snaphot(path)
            self.parent.SwnpSend('SYS', 'screenshot;0')
            if diwavars.AUDIO:
                logger.debug("Buffering audio for %d seconds" %
                                 diwavars.WINDOW_TAIL)
                self.parent.status_text.SetLabel("Recording...")
                wx.CallLater(diwavars.WINDOW_TAIL * 1000,
                             self.parent.audio_recorder.save,
                             ide, path)
        except:
            logger.exception("Create Event exception")

    def run(self):
        while not self._stop.isSet():
            pass
