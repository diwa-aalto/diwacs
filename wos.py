"""
Created on 8.5.2012

:author: neriksso

"""
from logging import config, getLogger
import os
from random import Random
import shutil
from subprocess import Popen
import sys
import threading
from time import sleep
import webbrowser
sys.stdout = open(r'data\stdout.log', 'wb')
sys.stderr = open(r'data\stderr.log', 'wb')


# 3rd party imports.
import configobj
from pubsub import pub
from urlparse import urlparse
from watchdog.observers import Observer
import wx
import wx.lib.buttons as buttons

try:
    from agw import ultimatelistctrl as ULC
#if it's not there locally, try the wxPython lib.
except ImportError:
    from wx.lib.agw import ultimatelistctrl as ULC

# Own imports.
import controller
from dialogs import (CloseError, ConnectionErrorDialog, PreferencesDialog,
                     ProjectSelectDialog)
import diwavars
import filesystem
import macro
from models import Company, Project
import swnp
from threads import (AudioRecorder, CONN_ERR_TH, WORKER_THREAD,
                     SEND_FILE_CONTEX_MENU_HANDLER, INPUT_CAPTURE,
                     CURRENT_SESSION, CURRENT_PROJECT, SetCapture)
import utils


config.fileConfig('logging.conf')
wos_logger = getLogger('wos')
CONTROLLED = False
CONTROLLING = False
VERSION_CHECKER = None


def SetLoggerLevel(level):
    """
    Used to set wos_logger level.

    :param level: The level desired.
    :type level: Integer

    """
    wos_logger.setLevel(level)


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


class DropTarget(wx.PyDropTarget):
    """
    Implements drop target functionality to receive files, bitmaps and text.

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
        Handles drag/dropping files/text or a bitmap.

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
    """
    Taskbar Icon class.

    :param parent: Parent frame
    :type parent: :class:`wx.Frame`

    """
    def __init__(self, parent):
        """
        Init tray.

        """
        wx.TaskBarIcon.__init__(self)
        self.parentApp = parent
        self.CreateMenu()

    def CreateMenu(self):
        """
        Create systray menu.

        """
        self.Bind(wx.EVT_TASKBAR_RIGHT_UP, self.ShowMenu)
        self.menu = wx.Menu()
        self.menu.Append(wx.ID_VIEW_LIST, "Select a Project")
        self.menu.Append(wx.ID_NEW, "Session")
        self.menu.Append(wx.ID_INDEX, "Open Project Dir")
        #self.menu.Append(wx.ID_HELP_INDEX, "TLDR")
        self.menu.Append(wx.ID_SETUP, "Preferences")
        self.menu.Append(wx.ID_ABOUT, "About")
        self.menu.AppendSeparator()
        self.menu.Append(wx.ID_EXIT, "Exit")

    def ShowMenu(self, event):
        """
        Show popup menu.

        :param event: GUI event.
        :type event: Event

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


class EventList(wx.Frame):
    """
    A Frame which displays the possible event titles and handles the event
    creation.

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
        """
        Fetches gui icons.

        :param icon: The icon file name.
        :type icon: String

        :rtype: :class:`wx.Image`

        """
        try:
            img = wx.Image('icons/' + icon + '.png', wx.BITMAP_TYPE_PNG)
            return img.ConvertToBitmap()
        except:
            return None


class GUI(wx.Frame):
    """
    WOS Application Frame.

    :param parent: Parent frame.
    :type parent: :class:`wx.Frame`

    :param title: Title for the frame
    :type title: String

    """

    def __init__(self, parent, title):
        """ Application initing """
        super(GUI, self).__init__(parent, title=title,
            size=diwavars.FRAME_SIZE, style=wx.FRAME_NO_TASKBAR)
        global DEFAULT_CURSOR, BLANK_CURSOR, WINDOWS_MAJOR, RUN_CMD
        self.init_screens_done = False
        wos_logger.debug("WxPython version %s" % (str(wx.VERSION)))
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
            self.worker.ParseConfig(self.config)
            self.swnp = swnp.SWNP(int(diwavars.PGM_GROUP),
                                  int(self.config['SCREENS']),
                                  self.config['NAME'],
                                  'observer' if self.is_responsive else "",
                                  error_handler=self.error_th)
        except Exception, e:
            wos_logger.exception("loading config exception %s", str(e))
        # if self.swnp.node.id == '3':
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
            #self.trayicon.Bind(wx.EVT_MENU, self.OnTLDR, id=wx.ID_HELP_INDEX)
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
            pub.subscribe(self.UpdateScreens, "update_screens")
            pub.subscribe(self.MessageHandler, "message_received")
            pub.sendMessage("update_screens", update=True)

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

    # def OnTLDR(self, event):
    #    event = event
    #    swnp.setTLDR(False)

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
        """
        Sends a file link to another node.

        """
        isFolder = os.path.isdir(filename)
        if isFolder:
            proj_fp = os.path.abspath(filename)
            proj_fp = proj_fp[proj_fp.rfind(os.path.sep):]
            if proj_fp.startswith(os.path.sep):
                proj_fp = proj_fp[1:]
            proj_remote = os.path.join(r'\\' +
                                       diwavars.STORAGE,
                                       'Projects', 'temp')
            cpid = self.current_project_id
            dial = wx.MessageDialog(None, 'Add ' + filename +
                                    ' folder to project?',
                                    'Adding files to project',
                                    wx.YES_NO | wx.NO_DEFAULT |
                                    wx.ICON_QUESTION | wx.STAY_ON_TOP)
            result = (dial.ShowModal() if self.current_project_id > 0
                      else wx.ID_NO)
            if (cpid and cpid > 0) and result == wx.ID_YES:
                proj_remote = controller.GetProjectPath(cpid)
            else:
                cpid = 0
            rdir = os.path.join(proj_remote, proj_fp)
            try:
                if not os.path.exists(rdir):
                    os.mkdir(os.path.join(rdir))
            except:
                wos_logger.exception('Failed to create ' +
                                     'folder for %s in %s' %
                                     (filename, rdir))
                return ''
            for root, dirs, files in os.walk(filename):
                proj_path = root[len(filename) - len(proj_fp):]
                proj_path = os.path.join(proj_remote,
                                         proj_path)
                try:
                    for d in dirs:
                        os.mkdir(os.path.join(proj_path, d))
                except Exception, e:
                    wos_logger.exception('Error %s', str(e))
                    continue
                for (source, target) in [
                            (os.path.join(root, fk),
                             os.path.join(proj_path, fk))
                            for fk in files]:
                    wos_logger.debug('Sending file: %s to %s' %
                                     (source, target))
                    try:
                        shutil.copyfile(source, target)
                        if cpid > 0:
                            controller.CreateFileaction(target, 1,
                                                    self.current_session_id,
                                                    cpid)
                    except Exception, e:
                        wos_logger.exception('Send file exception: %s', str(e))
            return rdir
        filepath = controller.IsProjectFile(filename, self.current_project_id)
        if not filepath:
            basename = os.path.basename(filename)
            dial = wx.MessageDialog(None, 'Add ' + basename + ' to project?',
                                    'Adding files to project',
                                    wx.YES_NO | wx.NO_DEFAULT |
                                    wx.ICON_QUESTION | wx.STAY_ON_TOP)
            result = (dial.ShowModal() if self.current_project_id > 0
                      else wx.ID_NO)
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
            """
            Opens project directory in windows explorer.

            :param evt: The GUI event.
            :type evt: Event

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
        """
        Set current session.

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
        """
        Start current project loop.

        :param project_id: The project id from database.
        :type project_id: Integer

        """
        global CURRENT_PROJECT_PATH
        global CURRENT_PROJECT_ID
        project_id = int(project_id)
        project = controller.GetProject(project_id)
        if not project:
                return
        if project and self.current_project_id != project_id:
            self.dirbtn.Disable()
            self.sesbtn.Disable()
            self.dirbtn.Enable(True)
            self.sesbtn.Enable(True)
            self.current_project_id = project_id
            wos_logger.debug("Set project label")
            wos_logger.debug("Project name is %s" % project.name)
            self.pro_label.SetLabel('Project: ' + project.name)
            self.worker.RemoveAllRegEntries()
            self.worker.AddProjectReg('*')
            self.worker.AddProjectReg('Folder')
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
            self.SetCurrentSession(0)
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
        """
        Create necessary db tables.

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
        """
        Session button pressed.

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
                showDialog = False
                if self.current_session_id != -1:
                    controller.EndSession(self.current_session_id)
                    showDialog = True
                self.current_session_id = 0
                self.current_session = None
                #self.SetCurrentProject(0)
                self.SwnpSend('SYS', 'current_session;0')
                #self.SwnpSend('SYS', 'current_project;0')
                controller.AddActivity(self.current_project_id,
                                       diwavars.PGM_GROUP, None, self.activity)
                self.SwnpSend('SYS', 'current_activity;' + str(self.activity))
                self.sesbtn.SetBitmapLabel(self.GetIcon('session_off'))
                if showDialog:
                    wos_logger.info('Session ended')
                    dlg = wx.MessageDialog(self, "Session ended!",
                                           'Information', wx.OK |
                                           wx.ICON_INFORMATION)
                    dlg.ShowModal()
                self.evtbtn.SetFocus()
            except Exception, e:
                wos_logger.exception("OnSession exception: %s", str(e))

    def StartCurrentProject(self):
        """
        Start current project loop.

        """
        if self.project_th:
            self.project_th.stop()
            self.project_th = None
        wos_logger.debug("Creating Current Project!")
        self.project_th = CURRENT_PROJECT(self.current_project_id,
                                          self.SwnpSend)
        self.project_th.daemon = True
        self.project_th.start()

    def StartCurrentSession(self):
        """
        Start current project loop.

        """
        if self.session_th:
            self.session_th.stop()
            self.session_th = None
        wos_logger.debug("Creating Current Session!")
        self.session_th = CURRENT_SESSION(self.current_session_id,
                                          self.SwnpSend)
        self.session_th.daemon = True
        self.session_th.start()

    def SelectProjectDialog(self, evt):
        """
        Select project event handler.

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
        """
        Preferences dialog event handler.

        :param evt: GUI Event.
        :type evt: Event

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
        """
        Loads a config file or creates one.

        """
        if not os.path.exists(diwavars.CONFIG_PATH):
            self.CreateConfig()
        return configobj.ConfigObj(diwavars.CONFIG_PATH)

    def CreateConfig(self):
        """
        Creates a config file.

        """
        if not os.path.exists(diwavars.CONFIG_PATH):
            try:
                os.makedirs(os.path.dirname(diwavars.CONFIG_PATH))
            except:
                pass
            shutil.copy('config.ini', diwavars.CONFIG_PATH)

    def GetIcon(self, icon):
        """
        Fetches gui icons.

        :param icon: The icon file name.
        :type icon: String

        :rtype: :class:`wx.Image`

        """
        return wx.Image('icons/' + icon + '.png',
                        wx.BITMAP_TYPE_PNG).ConvertToBitmap()

    def SwnpSend(self, node, message):
        """
        Sends a message to the node.

        :param node: The node for which to send a message.
        :type node: String

        :param message: The message.
        :type message: String

        """
        try:
            self.swnp.send(node, 'MSG', message)
        except:
            wos_logger.exception("SwnpSend exception %s to %s" %
                                 (message, node))

    def InitUI(self):
        """
        UI initing.

        """
        self.EXITED = False
        wos_logger.debug('call savescreen!')
        img_path = os.path.join(r'\\' + diwavars.STORAGE, 'SCREEN_IMAGES',
                                self.swnp.node.id + '.png')
        filesystem.SaveScreen((diwavars.WINDOWS_MAJOR, diwavars.WINDOWS_MINOR),
                              img_path)
        self.screens = wx.BoxSizer(wx.HORIZONTAL)
        self.InitScreens()
        # Subscribe handlers
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
        # pub.sendMessage("update_screens", update=True)
        self.Refresh()

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
        """
        Event Button handler.

        :param evt: GUI Event.
        :type evt: Event

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
        """
        Caroussel Shift function.

        :param evt: GUI Event.
        :type evt: Event

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
        """
        Observer for created files in scanned or taken with camera.

        """
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
        """
        Observer for filechanges in project directory.

        """
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
        """
        Project selected event handler.

        """
        controller.InitSyncProjectDir(self.current_project_id)
        self.activity = controller.AddActivity(self.current_project_id,
                                               diwavars.PGM_GROUP,
                                               self.current_session_id,
                                               self.activity)
        self.SwnpSend('SYS', 'current_activity;' + str(self.activity))
        self.Refresh()

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
        """
        Paints the selection of a node.

        .. note:: For future use.

        :param evt: GUI Event
        :type evt: Event

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
        """
        Handles the selection of a node, start remote control.

        .. note:: For future use.

        :param evt: GUI Event
        :type evt: Event

        """
        global MOUSE_X, MOUSE_Y
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
            SetCapture(False)
            self.capture_thread.unhook()
            self.overlay.Hide()
        else:
            # Start remote
            SetCapture(True)
            self.capture_thread.ResetMouseEvents()
            self.capture_thread.hook()
            self.SwnpSend(id_, 'remote_start;%s' % self.swnp.id)
            MOUSE_X, MOUSE_Y = evt.GetPositionTuple()
            self.selected_nodes.append(id_)
            self.Refresh()
            self.overlay.Show()

    def InitScreens(self):
        """
        Inits Screens.

        """
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
        """
        Aligns frame to Horizontal center and vertical top.

        """
        dw = wx.DisplaySize()[0]
        w = self.GetSize()[0]
        x = (dw - w) / 2
        self.SetPosition((x, 0))

    def HideScreens(self):
        """
        Hides all screens.

        """
        self.right.SetBitmapLabel(self.GetIcon('0'))
        self.left.SetBitmapLabel(self.GetIcon('0'))
        for i in self.imgs:
            temp = wx.Image(diwavars.NO_SCREEN, wx.BITMAP_TYPE_PNG)
            i.SetBitmap(temp.ConvertToBitmap())
            i.SetToolTip(None)

    def UpdateScreens(self, update):
        """
        Called when screens need to be updated and redrawn.

        :param update: Pubsub needs one param, therefore it is called update.
        :type update: Boolean

        """
        update = update  # Intentionally left unused.
        if not self.init_screens_done:
            return
        self.HideScreens()
        self.nodes = []
        for node in self.swnp.get_screen_list():
            try:
                self.nodes.append((node.id, node.screens, node.name))
                self.worker.AddRegEntry(name=node.name, node_id=node.id)
            except:
                pass
        if len(self.nodes):
            if len(self.nodes) > 3:
                self.left.SetBitmapLabel(self.GetIcon('left_arrow'))
                self.right.SetBitmapLabel(self.GetIcon('right_arrow'))
            for i in xrange(0,  min(diwavars.MAX_SCREENS, len(self.nodes))):
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
                    wos_logger.exception("nodes update except: %s", msg)
        self.worker.CheckResponsive()
        self.Refresh()

    def OnExit(self, event):
        """
        Exits program.

        :param event: GUI Event
        :type event: Event

        """
        if not self.EXITED:
            try:
                self.EXITED = True
                self.overlay.Destroy()
                self.Hide()
                self.trayicon.RemoveIcon()
                self.trayicon.Destroy()
                del self.trayicon
                self.closebtn.SetToolTip(None)
                if not event == 'conn_err' and self.is_responsive:
                    wos_logger.debug("On exit self is responsive")
                    self.RemoveObservers()
                    # controller.EndSession(self.current_session_id)
                    # controller.UnsetActivity(diwavars.PGM_GROUP)
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
                self.swnp.close()
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
        """
        About dialog.

        :param e: GUI Event.
        :type e: Event

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
        """
        Window minimize event handler.

        :param evt: GUI Event.
        :type evt: Event

        """
        if self.IsIconized():
            self.Show()
            self.Raise()
            self.SetFocus()
            self.Iconize(False)
            self.Refresh()
        else:
            self.Hide()
            self.Iconize(True)

    def OnTaskBarActivate(self, evt):
        """
        Taskbar activate event handler.

        :param evt: GUI Event.
        :type evt: Event

        """
        evt = evt
        if self.IsIconized():
            # The user wants to unminimize the application.
            self.Show()
            self.Raise()
            self.SetFocus()
            self.Iconize(False)
            self.Refresh()
        # elif app.IsActive() or self.HasFocus():  # Does work...
        else:
            # The user wants to minimize the application.
            self.Hide()
            self.Iconize(True)
        """
        else:
            # The user wants to bring the window to front.
            self.Raise()
            self.SetFocus()

        """

    def OnTaskBarClose(self, unused_event):
        """
        Taskbar close event handler.

        :param evt: GUI Event.
        :type evt: Event

        """
        wx.CallAfter(self.Close)

    def MessageHandler(self, message):
        """
        Message handler for received messages.

        :param message: Received message.
        :type message: an instance of :class:`swnp.Message`

        """
        global CONTROLLED, CONTROLLING
        try:
            # if diwavars.DEBUG:
            wos_logger.debug('ZMQ PUBSUB Message:' + message)
            cmd, target = message.split(';')
            if cmd == 'open':
                """ Open all files in list """
                target = eval(target)
                wos_logger.debug('open;' + str(target))
                for f in target:
                    if os.path.exists(f):
                        csid, cpid = (self.current_session_id,
                                      self.current_project_id)
                        if self.current_session_id:
                            try:
                                controller.CreateFileaction(f, 6, csid, cpid)
                            except Exception, e:
                                wos_logger.exception('CreateFileAction: %s' %
                                                     str(e))
                        filesystem.OpenFile(f)
            if cmd == 'new_responsive':
                if self.is_responsive:
                    self.StopResponsive()
                    self.is_responsive = False
                    self.responsive = target
            if cmd == 'event':
                if self.is_responsive:
                    self.worker.CreateEvent(target)
            if cmd == 'key':
                e, key, scan = target.split(',')
                e = int(e)
                flags = 0
                if e == 257:
                    flags = 2
                macro.SendInput('k', int(key), flags, int(scan))
            if cmd == 'remote_start':
                CONTROLLED = target
            if cmd == 'remote_end':
                if CONTROLLED:
                    #release alt
                    macro.SendInput('k', 18, 2, 56)
                if CONTROLLING:
                    self.SetCursor(DEFAULT_CURSOR)
                    del self.selected_nodes[:]
                    SetCapture(False)
                    self.capture_thread.unhook()
                    self.overlay.Hide()
                CONTROLLED = False
                CONTROLLING = False
            if cmd == 'mouse_move':
                x, y = target.split(',')
                macro.SendInput('m', [int(x), int(y)], 0x0001)
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
                macro.SendInput('m', [0, 0], flags, scan=0,
                                mouse_data=mouseData)
            if cmd == 'url':
                webbrowser.open(target)
            if cmd == 'set' and target == 'responsive':
                if not diwavars.RESPONSIVE == 0:
                    self.SetResponsive()
                    self.is_responsive = True
            if cmd == 'screenshot':
                if self.swnp.node.screens > 0:
                    pPath = controller.GetProjectPath(self.current_project_id)
                    filesystem.ScreenCapture(pPath, self.swnp.node.id)
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
    wos_logger.info('\n\n\n')
    wos_logger.info('Application started')
    app = wx.App()
    w = GUI(parent=None, title=(diwavars.APPLICATION_NAME + ' ' +
                                diwavars.VERSION))
    app.MainLoop()
