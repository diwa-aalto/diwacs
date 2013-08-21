"""
Created on 6.6.2013

:author: neriksso
:synopsis:
    This file represents graphical designs of some GUI elements in DiWaCS.

"""
# System imports.
from base64 import b64encode
import cStringIO
from logging import config, getLogger
import os

# Third party imports.
import wx
import wx.lib.buttons as buttons
from urlparse import urlparse
from sqlalchemy.exc import SQLAlchemyError
from modelsbase import ItemAlreadyExistsException
from wx._controls import TE_READONLY
try:
    from agw import ultimatelistctrl as ULC  # @UnusedImport
except ImportError:
    from wx.lib.agw import ultimatelistctrl as ULC  # @UnusedImport

# Own imports.
from dialogs import ConnectionErrorDialog, SendProgressBar
import diwavars
import filesystem
from models import File
import threading


LOGGER = None

# "Too many" public method (because wxPython 'derived'-classes are inherited).
# pylint: disable=R0904


def __init_logger():
    """
    Used to initialize the logger, when running from diwacs.py

    """
    global LOGGER
    config.fileConfig('logging.conf')
    LOGGER = getLogger('graphicaldesign')


def __set_logger_level(level):
    """
    Sets the logger level for graphicaldesign logger.

    :param level: Level of logging.
    :type level: Integer

    """
    LOGGER.setLevel(level)


diwavars.add_logger_initializer(__init_logger)
diwavars.add_logger_level_setter(__set_logger_level)


class ImageViewer(wx.Frame):
    """
    Used to show an image.

    """
    def __init__(self, parent, image, *args, **kwargs):
        wx.Frame.__init__(self, parent, wx.ID_ANY, 'wx_image viewer',
                          style=0, *args, **kwargs)
        menu = wx.MenuBar()
        file_menu = wx.Menu()
        self.save_button = file_menu.Append(wx.ID_SAVEAS, '&Save',
                                            'Save the image.')
        self.exit_button = file_menu.Append(wx.ID_EXIT, 'E&xit',
                                            'Close the image viewer.')
        menu.Append(file_menu)
        self.SetMenuBar(menu)
        bitmap = wx.BitmapFromImage(image)
        self.static_bitmap = wx.StaticBitmap(parent=self, id=wx.ID_ANY,
                                             bitmap=bitmap)
        self.Fit()
        self.Show()
        self.Raise()


class BlackOverlay(wx.Frame):
    """
    Represents all black frame without a mouse.

    """
    def __init__(self, pos, size, parent, text):
        wx.Frame.__init__(self, parent, wx.ID_ANY, '', pos=pos, size=size,
                          style=0)  # style=wx.STAY_ON_TOP)
        self.panel = wx.Panel(self, -1, size=size)
        pos = [x / 2 for x in wx.DisplaySize()]
        self.exit_label = wx.StaticText(self.panel, -1, label=text,
                                        style=wx.ALIGN_CENTER)
        font = wx.Font(32, wx.DECORATIVE, wx.ITALIC, wx.NORMAL)
        self.exit_label.SetFont(font)
        self.exit_label.SetForegroundColour('white')
        self.SetBackgroundColour('black')
        self.SetTransparent(200)
        self.parent = parent
        self.SetCursor(diwavars.BLANK_CURSOR)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnFocusLost)

    def OnFocusLost(self, evt):
        """
        Event handler for focus losing of the window.

        :param evt: The focus lost event.
        :type evt: :py:class:`wx.Event`

        """
        if self.IsShown():
            evt.Skip(False)
            self.parent.panel.SetFocus()
        else:
            evt.Skip(True)

    def SetText(self, button_modifier=None, button=None):
        if not button_modifier:
            button_modifier = 'ALT'
        if not button:
            button = 'ESC'
        replaces = {
            'MENU': 'ALT',
            'BACK': 'BACKSPACE'
        }
        button_modifier = button_modifier.upper()
        button = button.upper()
        hotkey_table = [button_modifier, button]
        for index, hotkey in enumerate(hotkey_table):
            if hotkey in replaces:
                hotkey_table[index] = replaces[hotkey]
        label_format = 'Press {0} + {1} to end remote control'
        label_text = label_format.format(hotkey_table[0], hotkey_table[1])
        self.exit_label.SetLabel(label_text)


class DropTarget(wx.PyDropTarget):
    """
    Implements drop target functionality to receive files, bitmaps and text.

    """
    def __init__(self, window, parent, i):
        wx.PyDropTarget.__init__(self)
        # the dataobject that gets filled with the appropriate data.
        self.dataobject = wx.DataObjectComposite()
        self.window = window
        self.parent = parent
        self.id_iterator = i
        self.filedo = wx.FileDataObject()
        self.textdo = wx.TextDataObject()
        self.bmpdo = wx.BitmapDataObject()
        self.dataobject.Add(self.filedo)
        self.dataobject.Add(self.bmpdo)
        self.dataobject.Add(self.textdo)
        self.SetDataObject(self.dataobject)
        self.my_send_dialogs = []

    def _OnFileProcedure(self, iterated, filenames):
        """
        Handle filesend in threaded manner.

        :param iterated: The node.
        :type iterated: :py:class:`swnp.Node`

        :param filenames: The filenames to send, can include folder names too.
        :type filenames: List of String

        """
        if not filenames:
            return
        try:
            deltay = 200
            for dialogy in self.my_send_dialogs:
                deltay = deltay if dialogy < deltay else dialogy
            deltay += 20
            self.my_send_dialogs.append(deltay)
            title = 'Sending items...'
            project = self.parent.diwa_state.current_project
            project_items = []
            paths = []
            if not project:
                paths.extend(filenames)
                filenames = []
            # Separate project files/folders from other stuff.
            #: TODO: CHECK PROJECT EXISTANCE!!!
            for filename in filenames:
                filename = os.path.abspath(filename)
                if filename.startswith(diwavars.PROJECT_PATH):
                    project_items.append(filename)
                    if not File.get('exists', File.path == filename):
                        try:
                            File(filename, project.id)
                        except (SQLAlchemyError, ItemAlreadyExistsException):
                            pass
                else:
                    paths.append(filename)
            # Process items that are not part of the project.
            if paths:
                params = {
                    'class': SendProgressBar,
                    'kwargs': {
                        'parent': self.parent,
                        'title': title,
                        'ypos': deltay
                    }
                }
                paths = self.parent.diwa_state.handle_file_send(paths, params)
            # Union the two lists again.
            paths.extend(project_items)
            self.parent.Show()
            self.parent.Raise()
            self.parent.Update()
            if paths:
                filenames = paths
            command = 'open;{0!s}'.format(filenames)
            self.parent.diwa_state.swnp_send(str(iterated), command)
            self.my_send_dialogs.remove(deltay)
        except Exception as excp:
            LOGGER.exception('OnData exception: {0} - {1!s}'.\
                             format(filenames, excp))

    def OnData(self, x, y, d):
        """
        Handles drag/dropping files/text or a bitmap.

        :param x: The x coordinate of the drop-location.
        :type x: Integer

        :param y: The y coordinate of the drop-location.
        :type y: Integer

        :param d: The data of drop.

        """
        if not self.GetData():
            return d
        try:
            data_type = self.dataobject.GetReceivedFormat().GetType()
            difference = self.id_iterator + self.parent.iterator
            node_id = self.parent.nodes[difference].id
            if data_type == wx.DF_BITMAP:
                bitmap = self.bmpdo.GetBitmap()
                image = bitmap.ConvertToImage()
                image_buffer = cStringIO.StringIO()
                image.SaveStream(image_buffer, wx.BITMAP_TYPE_PNG)
                image_data = image_buffer.getvalue()
                msg = 'wx_image;{0}'.format(b64encode(image_data))
                self.parent.diwa_state.swnp_send(str(node_id), msg)
                LOGGER.debug('Sent wx_image to {0} with length {1}'.\
                             format(node_id, len(msg) - len('wx_image;')))
                image_buffer.close()
            if data_type in [wx.DF_UNICODETEXT, wx.DF_TEXT]:
                text = self.textdo.GetText()
                parsed = urlparse(text)
                if parsed.scheme == 'http' or parsed.scheme == 'https':
                    msg = 'url;' + text
                    self.parent.diwa_state.swnp_send(str(node_id), msg)
            elif data_type == wx.DF_FILENAME:
                filenames = self.filedo.GetFilenames()
                data_target = self._OnFileProcedure
                data_thread = threading.Thread(target=data_target,
                                               name='on_data',
                                               args=[node_id, filenames])
                data_thread.run()
            else:
                LOGGER.debug('Unknown file-drop format: {0!s}'.\
                             format(data_type))
        except (ValueError, IOError, OSError) as excp:
            LOGGER.exception('Error while sending items: {0!s}'.format(excp))
        finally:
            return d  # you must return this


class EventListTemplate(wx.Frame):
    """
    Represents an event list menu.

    """
    def __init__(self, parent, *args, **kwargs):
        self.parent = parent
        display_width = wx.DisplaySize()[0]
        width, height = diwavars.FRAME_SIZE
        pos_x = ((display_width - width) / 2) + width
        pos_y = height / 2
        wx.Frame.__init__(self, parent, -1, pos=(pos_x, pos_y),
                          style=wx.FRAME_FLOAT_ON_PARENT |
                          wx.FRAME_NO_TASKBAR, *args, **kwargs)
        self.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.event_menu_titles = ['Important', 'Decision', 'Action Point',
                                  'Discussion', 'Future Agenda']
        image_list = wx.ImageList(32, 32, True)
        for event_title in self.event_menu_titles:
            event_title = event_title.lower().replace(" ", "_")
            image_list.Add(self.GetProgramIcon(event_title))
        msize = len(self.event_menu_titles) * 38
        self.evtlist = ULC.UltimateListCtrl(self, -1, agwStyle=wx.LC_REPORT |
                                            wx.LC_NO_HEADER |
                                            ULC.ULC_NO_HIGHLIGHT,
                                            size=(210, msize))
        info = ULC.UltimateListItem()
        info.SetMask(wx.LIST_MASK_TEXT | wx.LIST_MASK_IMAGE |
                     wx.LIST_MASK_FORMAT | ULC.ULC_MASK_CHECK)
        info.SetImage([])
        info.SetFooterFormat(0)
        info.SetFooterKind(0)
        info.SetText('Icon')

        self.evtlist.InsertColumnInfo(0, info)
        self.evtlist.AssignImageList(image_list, wx.IMAGE_LIST_SMALL)
        for idx, item in enumerate(self.event_menu_titles):
            self.evtlist.InsertImageStringItem(idx, item, idx, it_kind=0)
        self.custom1_id = -1
        self.evtlist.SetColumnWidth(0, 200)
        self.custom_icon = wx.StaticBitmap(self, -1,
                                           self.GetProgramIcon('custom3'))
        self.custom_event = wx.TextCtrl(self, -1, size=(177, -1))
        self.on_text = False
        self.custom_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.custom_sizer.Add(self.custom_icon, 0)
        self.custom_sizer.Add(self.custom_event, 0, wx.EXPAND)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.evtlist, 0)
        self.sizer.Add(self.custom_sizer, 0)
        self.SetSizer(self.sizer)
        self.selection_made = 0
        self.sizer.Fit(self)

    def GetProgramIcon(self, icon):
        """
        Fetches gui icons.

        :param icon: The icon file name.
        :type icon: String

        :rtype: :class:`wx.Image`

        """
        try:
            img = wx.Image('icons/' + icon + '.png', wx.BITMAP_TYPE_PNG)
            return img.ConvertToBitmap()
        except (ValueError, IOError, OSError):
            return None


class MySplashScreen(wx.SplashScreen):
    """
    Create a splash screen widget.

    """
    def __init__(self, parent=None):
        bitmap = wx.Image(name=os.path.join('data', 'splashscreen.png'))
        bitmap = bitmap.ConvertToBitmap()
        splash_style = wx.SPLASH_CENTRE_ON_SCREEN | wx.SPLASH_NO_TIMEOUT
        splash_duration = 800  # milliseconds
        wx.SplashScreen.__init__(self, bitmap, splash_style, splash_duration,
                                 parent)


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
        self.menu = None
        self.CreateMenu()

    def CreateMenu(self):
        """
        Create systray menu.

        """
        self.Bind(wx.EVT_TASKBAR_RIGHT_UP, self.ShowMenu)
        self.menu = wx.Menu()
        self.menu.Append(wx.ID_VIEW_LIST, 'Select a Project')
        self.menu.Append(wx.ID_NEW, 'Session')
        self.menu.Append(wx.ID_INDEX, 'Open Project Directory')
        self.menu.Append(wx.ID_SETUP, 'Preferences')
        self.menu.Append(wx.ID_ABOUT, 'About')
        self.menu.AppendSeparator()
        self.menu.Append(wx.ID_EXIT, 'Exit')

    def ShowMenu(self, event):
        """
        Show popup menu.

        :param event: GUI event.
        :type event: Event

        """
        event = event
        self.PopupMenu(self.menu)

    def ShowNotification(self, title, message):
        """
        Start a thread to show the notification.

        :param title: Title to diplay in the balloon.
        :type title: Unicode

        :param message: Message to display in the balloong (max 255 chars).
        :type message: Unicode

        """
        args = [title, message]
        notify_thread = threading.Thread(target=self._show_notification,
                                         name='Notification', args=args)
        notify_thread.run()

    def _show_notification(self, title, message):
        """
        Thread routine for the balloontip.

        :param title: Title to diplay in the balloon.
        :type title: String

        :param message: Message to display in the balloong (max 255 chars).
        :type message: String

        """
        self.ShowBalloon(title, message, 10000, wx.ICON_NONE)


class NodeScreen(wx.StaticBitmap):
    """
    Represents a bitmap with node id.

    """
    DEFAULT_BITMAP = None
    EMPTY_BITMAP = None

    @staticmethod
    def update_bitmaps():
        NodeScreen.DEFAULT_BITMAP = wx.Bitmap(diwavars.DEFAULT_SCREEN,
                                              wx.BITMAP_TYPE_ANY)
        NodeScreen.EMPTY_BITMAP = wx.Bitmap(diwavars.NO_SCREEN,
                                            wx.BITMAP_TYPE_ANY)

    def __init__(self, node, parent):
        wx.StaticBitmap.__init__(self, parent)
        self.node = node
        self.gdot = wx.StaticBitmap(self, bitmap=wx.Bitmap(diwavars.GREEN_DOT,
                                            wx.BITMAP_TYPE_PNG),
                                            pos=(88, 61))
        self.gdot.Hide()
        self.ydot = wx.StaticBitmap(self, bitmap=wx.Bitmap(diwavars.YELLOW_DOT,
                                            wx.BITMAP_TYPE_PNG),
                                            pos=(98, 61))
        self.ydot.Hide()
        self.rdot = wx.StaticBitmap(self, bitmap=wx.Bitmap(diwavars.RED_DOT,
                                            wx.BITMAP_TYPE_PNG),
                                            pos=(108, 61))
        self.rdot.Hide()
        self.EmptyScreen()

    def EmptyScreen(self):
        """ Make this screen EmptyScreen. """
        for dot in [self.rdot, self.ydot, self.gdot]:
            dot.Hide()
        self.node = None
        self.SetBitmap(NodeScreen.EMPTY_BITMAP)
        self.SetToolTip(None)

    def ReloadAs(self, node):
        """ Reload the content of this bitmap. """
        if not node:
            self.EmptyScreen()
            return
        if self.node is not None and self.node.id == node.id:
            self.node = node
            self.SetNodeVars()
            self.Show()
            return
        self.node = node
        bitmap = NodeScreen.DEFAULT_BITMAP
        try:
            img = filesystem.get_node_image(self.node.id)
            bitmap = wx.Bitmap(img, wx.BITMAP_TYPE_ANY)
        except IOError:
            pass
        self.SetBitmap(bitmap)
        self.SetNodeVars()
        self.Refresh()

    def SetNodeVars(self):
        """
        Sets NodeScreens variables.

        """
        # LOGGER.debug('Node data {0}'.format(self.node.data))
        if 'controlled' in self.node.data:
            self.ydot.Show()
            self.gdot.Hide()
        else:
            self.ydot.Hide()
            self.gdot.Show()
        if 'audio' in self.node.data:
            self.rdot.Show()
        else:
            self.rdot.Hide()
        tooltip = wx.ToolTip(self.node.name)
        self.SetToolTip(tooltip)


class GUItemplate(wx.Frame):
    """
    Represents the main GUI window graphical template.

    :param parent: Parent frame.
    :type parent: :class:`wx.Window`

    :param id: ID of the new Frame.
    :type id: Integer

    :param title: Title for the frame, default = EmptyString.
    :type title: String

    :param pos: Position of the new frame.
    :type pos: wx.Point

    :param size: Size of the new frame.
    :type size: wx.Size

    :param style: Style flags for the new frame.
    :type style: long

    :param name: Name of  the new frame.
    :type name: String

    """
    def __init__(self, *args, **kwargs):
        wx.Frame.__init__(self, *args, **kwargs)
        self.SetDoubleBuffered(True)
        self.filedrops = []
        self.nodes = []
        self.node_screens = []
        self.iterator = 0
        self.selected_nodes = []
        self.init_screens_done = False
        self.panel = wx.Panel(self, -1, size=(diwavars.FRAME_SIZE[0],
                                              diwavars.FRAME_SIZE[1] - 50))
        self.panel.SetBackgroundColour(wx.Colour(202, 235, 255))
        self.overlay = None
        self.exited = None
        self.screens = None
        self.pro_label = None
        self.probtn = None
        self.dirbtn = None
        self.sesbtn = None
        self.setbtn = None
        self.hidebtn = None
        self.closebtn = None
        self.left = None
        self.right = None
        self.evtbtn = None
        self.banner_panel = None
        self.logo = None
        self.diwawabtn = None
        self.diwambbtn = None
        self.status_text = None
        self.banner = None
        self.infobtn = None

    def AlignCenterTop(self):
        """
        Aligns frame to Horizontal center and vertical top.

        """
        display_width = wx.DisplaySize()[0]
        width = self.GetSize()[0]
        pos_x = (display_width - width) / 2
        self.SetPosition((pos_x, 0))

    def ClearStatusText(self):
        """
        Sets the status text to EmptyScreen string.

        """
        self.status_text.SetLabel('')

    def ConnectionErrorHandler(self, error):
        """
        Show connection error handler dialog.

        """
        error = error
        dialog = ConnectionErrorDialog(self)
        result = dialog.GetResult()
        dialog.Destroy()
        if result:
            self.OnExit('conn_err')

    def GetProgramIcon(self, icon):
        """
        Fetches a GUI icon.

        :param icon: The icon file name.
        :type icon: String

        :rtype: :class:`wx.Image`

        """
        img = wx.Image('icons/' + icon + '.png', wx.BITMAP_TYPE_PNG)
        return img.ConvertToBitmap()

    def HideScreens(self):
        """
        Hides all screens.

        """
        for node_screen in self.node_screens:
            node_screen.EmptyScreen()
            node_screen.Disable()

    def InitScreens(self):
        """
        Inits Screens.

        """
        LOGGER.debug('init screens start')
        try:
            for i in xrange(diwavars.MAX_SCREENS):
                sbox = wx.BoxSizer(wx.VERTICAL)
                screen = NodeScreen(node=None, parent=self.panel)
                screen.Bind(wx.EVT_LEFT_DOWN, self.SelectNode)
                self.node_screens.insert(i, screen)
                drop_target = DropTarget(screen, self, i)
                screen.SetDropTarget(drop_target)
                screen.Disable()
                screen.Show()
                self.filedrops.insert(i, drop_target)
                sbox.Add(screen)
                self.screens.Add(sbox, 0, wx.LEFT | wx.RIGHT, border=3)
        except Exception as excp:
            LOGGER.exception('Init screens exception: {0!s}'.format(excp))
        self.Layout()
        self.Refresh()
        self.init_screens_done = True

    def InitUI(self, node_id):
        """
        UI initializing.

        :param node_id: The id of current swnp node (self).
        :type node_id: Integer

        """
        self.exited = False
        LOGGER.debug('Call savescreen!')
        img_path = os.path.join(r'\\' + diwavars.STORAGE, 'SCREEN_IMAGES',
                                str(node_id) + '.png')
        try:
            filesystem.save_screen(img_path)
        except Exception as excp:
            LOGGER.exception('save_screen exception: {0!s}'.format(excp))
        self.screens = wx.BoxSizer(wx.HORIZONTAL)
        self.InitScreens()

        # Create UI
        try:
            vbox = wx.BoxSizer(wx.VERTICAL)
            btnsizer = wx.BoxSizer(wx.HORIZONTAL)
            icon = self.GetProgramIcon

            self.pro_label = wx.TextCtrl(self.panel, -1, 'No Project Selected',
                                         style=wx.TE_READONLY | wx.TE_CENTRE)
            self.pro_label.SetBackgroundColour(wx.Colour(2, 235, 255))
            myfont = self.pro_label.Font
            myfont.SetPointSize(myfont.GetPointSize() + 2)
            self.pro_label.Font = myfont
            btnsizer.Add(self.pro_label, 1, wx.EXPAND)
            self.probtn = buttons.GenBitmapButton(self.panel, wx.ID_ANY,
                                                  icon('button1'),
                                                  size=(-1, 32),
                                                  style=wx.NO_BORDER)
                                                # ,style=wx.BU_LEFT
            self.probtn.SetBackgroundColour(self.panel.GetBackgroundColour())
            self.probtn.focusClr = self.panel.GetBackgroundColour()
            self.probtn.shadowPenClr = self.panel.GetBackgroundColour()
            self.probtn.highlightPenClr = self.panel.GetBackgroundColour()
            self.probtn.faceDnClr = self.panel.GetBackgroundColour()
            self.probtn.SetToolTip(wx.ToolTip('Select a project'))
            btnsizer.Add(self.probtn, 0)
            self.dirbtn = buttons.GenBitmapButton(self.panel, wx.ID_ANY,
                                                  icon('folder'),
                                                  size=(-1, 32),
                                                  style=wx.NO_BORDER)
            self.dirbtn.SetBackgroundColour(self.panel.GetBackgroundColour())
            self.dirbtn.focusClr = self.panel.GetBackgroundColour()
            self.dirbtn.shadowPenClr = self.panel.GetBackgroundColour()
            self.dirbtn.highlightPenClr = self.panel.GetBackgroundColour()
            self.dirbtn.faceDnClr = self.panel.GetBackgroundColour()
            self.dirbtn.SetToolTip(wx.ToolTip('Open Project Directory'))
            self.dirbtn.Disable()
            btnsizer.Add(self.dirbtn, 0)
            self.sesbtn = buttons.GenBitmapButton(self.panel, wx.ID_ANY,
                                                  icon('session_off'),
                                                  size=(-1, 32))
            self.sesbtn.SetBackgroundColour(self.panel.GetBackgroundColour())
            self.sesbtn.focusClr = self.panel.GetBackgroundColour()
            self.sesbtn.shadowPenClr = self.panel.GetBackgroundColour()
            self.sesbtn.highlightPenClr = self.panel.GetBackgroundColour()
            self.sesbtn.faceDnClr = self.panel.GetBackgroundColour()
            self.sesbtn.SetToolTip(wx.ToolTip('Toggle Session'))
            self.sesbtn.Disable()
            btnsizer.Add(self.sesbtn, 0, wx.LEFT | wx.RIGHT, 10)
            self.setbtn = buttons.GenBitmapButton(self.panel, wx.ID_ANY,
                                                  icon('settings'),
                                                  size=(-1, 32))
            #self.setbtn.SetBitmap(self.GetProgramIcon('settings'))
            self.setbtn.SetBackgroundColour(self.panel.GetBackgroundColour())
            self.setbtn.focusClr = self.panel.GetBackgroundColour()
            self.setbtn.shadowPenClr = self.panel.GetBackgroundColour()
            self.setbtn.highlightPenClr = self.panel.GetBackgroundColour()
            self.setbtn.faceDnClr = self.panel.GetBackgroundColour()
            self.setbtn.SetToolTip(wx.ToolTip('Settings'))
            btnsizer.Add(self.setbtn, 0, wx.LEFT | wx.RIGHT, 1)
            self.hidebtn = buttons.GenBitmapButton(self.panel,
                                                   wx.ID_ICONIZE_FRAME,
                                                   icon('minimize'),
                                                   size=(32, 32),
                                                   style=wx.NO_BORDER)
            self.hidebtn.SetBackgroundColour(self.panel.GetBackgroundColour())
            self.hidebtn.focusClr = self.panel.GetBackgroundColour()
            self.hidebtn.shadowPenClr = self.panel.GetBackgroundColour()
            self.hidebtn.highlightPenClr = self.panel.GetBackgroundColour()
            self.hidebtn.faceDnClr = self.panel.GetBackgroundColour()
            self.hidebtn.SetToolTip(wx.ToolTip('Minimize'))
            btnsizer.Add(self.hidebtn, 0, wx.LEFT, 1)
            self.closebtn = buttons.GenBitmapButton(self.panel, wx.ID_CLOSE,
                                                    icon('close'),
                                                    size=(32, 32),
                                                    style=wx.NO_BORDER)
            self.closebtn.SetBackgroundColour(self.panel.GetBackgroundColour())
            self.closebtn.focusClr = self.panel.GetBackgroundColour()
            self.closebtn.shadowPenClr = self.panel.GetBackgroundColour()
            self.closebtn.highlightPenClr = self.panel.GetBackgroundColour()
            self.closebtn.faceDnClr = self.panel.GetBackgroundColour()
            self.closebtn.SetToolTip(wx.ToolTip('Exit'))
            btnsizer.Add(self.closebtn, 0, wx.RIGHT, 1)
        except Exception as excp:
            LOGGER.exception('UI exception: {0!s}'.format(excp))

        vbox.Add(btnsizer, 0, wx.EXPAND | wx.BOTTOM, 3)
        screenSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.left = buttons.GenBitmapButton(self.panel, wx.ID_BACKWARD,
                                            icon('left_arrow'),
                                            style=wx.NO_BORDER)
        self.left.SetBackgroundColour(self.panel.GetBackgroundColour())
        self.left.focusClr = self.panel.GetBackgroundColour()
        self.left.shadowPenClr = self.panel.GetBackgroundColour()
        self.left.highlightPenClr = self.panel.GetBackgroundColour()
        self.left.faceDnClr = self.panel.GetBackgroundColour()
        self.right = buttons.GenBitmapButton(self.panel, wx.ID_FORWARD,
                                             icon('right_arrow'),
                                             style=wx.NO_BORDER)
        self.right.SetBackgroundColour(self.panel.GetBackgroundColour())
        self.right.focusClr = self.panel.GetBackgroundColour()
        self.right.shadowPenClr = self.panel.GetBackgroundColour()
        self.right.highlightPenClr = self.panel.GetBackgroundColour()
        self.right.faceDnClr = self.panel.GetBackgroundColour()
        xflags = (wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL | wx.RIGHT |
                  wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        self.left.Disable()
        self.right.Disable()
        screenSizer.Add(self.left, 0, xflags, 2)
        screenSizer.Add(self.screens, 0, wx.EXPAND, 0)
        screenSizer.Add(self.right, 0, xflags, 2)

        self.evtbtn = buttons.GenBitmapButton(self.panel, wx.ID_ANY,
                                              icon('action'),
                                              size=(75, 75),
                                              style=wx.NO_BORDER)
        self.evtbtn.SetBackgroundColour(self.panel.GetBackgroundColour())
        self.evtbtn.focusClr = self.panel.GetBackgroundColour()
        self.evtbtn.shadowPenClr = self.panel.GetBackgroundColour()
        self.evtbtn.highlightPenClr = self.panel.GetBackgroundColour()
        self.evtbtn.faceDnClr = self.panel.GetBackgroundColour()
        self.evtbtn.SetToolTip(wx.ToolTip('Create Event'))
        self.evtbtn.Disable()

        # Setting Bottom Banner
        self.banner_panel = wx.Panel(self,
                                     pos=(0, diwavars.FRAME_SIZE[1] - 50),
                                     size=(diwavars.FRAME_SIZE[0], 50))
        self.banner_panel.SetBackgroundColour(wx.Colour(45, 137, 255))
        self.logo = wx.StaticBitmap(self.banner_panel, id=wx.ID_ANY,
                                    bitmap=icon('logo'), pos=(5, 0))
        self.diwawabtn = buttons.GenBitmapButton(self.banner_panel, wx.ID_ANY,
                                                 icon('diwawa'),
                                                 style=wx.NO_BORDER,
                                                 pos=(95, 4),
                                                 size=(81, 32))
        self.diwawabtn.focusClr = wx.Colour(45, 137, 255)
        self.diwawabtn.shadowPenClr = wx.Colour(45, 137, 255)
        self.diwawabtn.highlightPenClr = wx.Colour(45, 137, 255)
        self.diwawabtn.faceDnClr = wx.Colour(45, 137, 255)
        self.diwawabtn.SetToolTip(wx.ToolTip('Web Application'))
        self.diwambbtn = buttons.GenBitmapButton(self.banner_panel, wx.ID_ANY,
                                                 self.GetProgramIcon('diwamb'),
                                                 style=wx.BORDER_NONE,
                                                 pos=(185, 4), size=(99, 33))
        self.diwambbtn.SetBackgroundColour(wx.Colour(45, 137, 255))
        self.diwambbtn.focusClr = wx.Colour(45, 137, 255)
        self.diwambbtn.shadowPenClr = wx.Colour(45, 137, 255)
        self.diwambbtn.highlightPenClr = wx.Colour(45, 137, 255)
        self.diwambbtn.faceDnClr = wx.Colour(45, 137, 255)
        self.diwambbtn.SetToolTip(wx.ToolTip('Meeting Browser'))
        #self.status_text = wx.StaticText(self.banner_panel, -1, '',
        #                                 pos=(diwavars.FRAME_SIZE[0] - 220, 0))
        self.banner = wx.StaticBitmap(self.banner_panel, id=wx.ID_ANY,
                                      bitmap=self.GetProgramIcon('balls'),
                                      pos=(diwavars.FRAME_SIZE[0] - 295, 0))
        # self.statusbg = wx.StaticBitmap(self.banner_panel, id=wx.ID_ANY,
        #                          bitmap=self.GetProgramIcon('statusbg'),
        #                          pos=(diwavars.FRAME_SIZE[0] - 150, 0),
        #                          size=(150,50))
        self.infobtn = buttons.GenBitmapButton(self.banner, wx.ID_ANY,
                                               icon('info'),
                                               style=wx.BORDER_NONE,
                                               pos=(80, 5), size=(20, 20))
        self.infobtn.SetBackgroundColour(wx.Colour(45, 137, 255))
        self.infobtn.focusClr = wx.Colour(45, 137, 255)
        self.infobtn.shadowPenClr = wx.Colour(45, 137, 255)
        self.infobtn.highlightPenClr = wx.Colour(45, 137, 255)
        self.infobtn.faceDnClr = wx.Colour(45, 137, 255)
        self.infobtn.SetToolTip(wx.ToolTip('Info'))
        msg = ' '.join(['DiWaCS', diwavars.VERSION])
        version = wx.StaticText(self.banner_panel, wx.ID_ANY, msg, pos=(5, 35),
                                style=wx.ALIGN_CENTRE)
        version.SetFont(wx.Font(7, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL,
                                wx.FONTWEIGHT_LIGHT))
        # TODO: Status box.
        self.status_box = wx.TextCtrl(self.banner_panel, wx.ID_ANY,
                                      pos=(diwavars.FRAME_SIZE[0] - 185, 5),
                                      size=(180, 40),
                                      style=wx.TE_MULTILINE | TE_READONLY)
        if not diwavars.STATUS_BOX_VALUE:
            self.status_box.Hide()
        diwavars.register_status_box_callback(self._OnStatusBoxCallback,
                                              self._OnStatusBoxPrint)
        screenSizer.Add(self.evtbtn, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 30)
        vbox.Add(screenSizer, 0)
        self.SetSizer(vbox)
        self.Layout()
        self.AlignCenterTop()
        self.Show()
        self.Refresh()

    def _OnStatusBoxCallback(self, value):
        if value:
            self.status_box.Show()
        else:
            self.status_box.Hide()

    def _OnStatusBoxPrint(self, value):
        if len(self.status_box.GetValue()):
            self.status_box.AppendText('\r\n')
        self.status_box.AppendText(value)

    def OnExit(self, event):
        """
        Exits program.

        :param event: GUI Event
        :type event: Event

        """
        pass

    def SelectNode(self, evt):
        """
        Handles the selection of a node, prototype.

        :param evt: GUI Event
        :type evt: Event

        """
        pass
