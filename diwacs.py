"""
Created on 8.5.2012

:author: neriksso

"""
# Critical imports
import sys
import diwavars

if __name__ == '__main__':
    diwavars.set_running()

# Standard imports.
from ast import literal_eval
import cProfile
import datetime
import logging
import os
import pstats
import StringIO
import threading
from time import sleep
import webbrowser
import inspect

# 3rd party imports.
from pubsub import pub
import pyHook
import wx


# Own imports.
import controller
from dialogs import (CloseError, PreferencesDialog, ProjectSelectDialog,
                     ErrorDialog, show_modal_and_destroy,
                     ChooseDiwaProfileDialog)
from graphicaldesign import (BlackOverlay, MySplashScreen, SysTray, NodeScreen,
                             GUItemplate, EventListTemplate)
from models import Project
import state
import threads
import utils


LOGGER = None

# "Too many" public method (because wxPython 'derived'-classes are inherited).
# pylint: disable=R0904


if __name__ == '__main__':
    # Load up the loggers for every module.
    global LOGGER
    try:
        os.makedirs(os.path.dirname(diwavars.CONFIG_PATH))
    except Exception:
        pass
    logging.config.fileConfig('logging.conf')
    LOGGER = logging.getLogger('diwacs')
    for logger_initializer in diwavars.LOGGER_INITIALIZER_LIST:
        logger_initializer()


def __set_logger_level(level):
    """
    Used to set logger level.

    :param level: The level desired.
    :type level: Integer

    """
    LOGGER.setLevel(level)


class EventList(EventListTemplate):
    """
    A Frame which displays the possible event titles and handles the event
    creation.

    """
    def __init__(self, parent, *args, **kwargs):
        EventListTemplate.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.evtlist.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelection)
        self.evtlist.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnSelection)
        self.custom_event.Bind(wx.EVT_SET_FOCUS, self.OnText)
        self.custom_event.Bind(wx.EVT_TEXT, self.OnText)
        self.custom_event.Bind(wx.EVT_TEXT_ENTER, self.OnEnter)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnFocusLost)

    def OnEnter(self, event):
        """
        Event handler for pressing ENTER button.

        :param event: The EVT_ON_TEXT_EVENT event.
        :type event: :py:class:`wx.Event`

        """
        LOGGER.debug('EventList.OnEnter()')
        label = self.custom_event.GetValue()
        project = self.parent.diwa_state.current_project
        session = self.parent.diwa_state.current_session
        if not self.parent.diwa_state.is_responsive:
            LOGGER.debug('EventList.OnEnter(-NOT RESPONSIVE-)')
            label = label.encode('utf-8')
            self.parent.diwa_state.swnp_send(self.parent.diwa_state.responsive,
                                             'event;{0}'.format(label))
        elif project and session:
            LOGGER.debug('EventList.OnEnter(CALL AFTER)')
            self.parent.diwa_state.send_print_to_status(unicode('Event: ' + label))
            wx.CallAfter(self.parent.diwa_state.worker.create_event, label)
        self.custom_event.SetValue('')
        wx.CallLater(1000, self.HideNow)
        LOGGER.debug('EventList.OnEnter(endish)')
        if event:
            event.Skip()
        LOGGER.debug('EventList.OnEnter(end)')

    def OnText(self, event):
        """
        On text event handler.

        """
        self.on_text = True
        if event:
            event.Skip()

    def OnFocusLost(self, event):
        """
        On focus lost event handler.

        """
        self.Hide()
        if event:
            event.Skip()

    def ShowNow(self):
        """
        Method to show the event list.

        """
        self.on_text = False
        self.Show()
        wx.CallLater(5000, self.CheckVisibility, self.selection_made)

    def HideNow(self):
        """
        Method to hide the event list.

        """
        self.Hide()
        index = self.evtlist.GetNextItem(-1)
        colour = wx.Colour(255, 255, 255)
        while index != -1:
            self.evtlist.SetItemBackgroundColour(index, colour)
            index = self.evtlist.GetNextItem(index)

    def OnSelection(self, event):
        """
        On selection event handler.

        """
        i = self.evtlist.GetNextSelected(-1)
        self.evtlist.SetItemBackgroundColour(i, wx.Colour(45, 137, 255))
        label = self.evtlist.GetItemText(i)
        LOGGER.debug('Custom event {0!s} responsive is {1!s}'.\
                     format(label, self.parent.diwa_state.responsive))
        self.evtlist.Select(i, False)
        self.selection_made += 1
        project = self.parent.diwa_state.current_project
        session = self.parent.diwa_state.current_session
        if not self.parent.diwa_state.is_responsive:
            self.parent.diwa_state.swnp_send(self.parent.diwa_state.responsive,
                                            'event;{0}'.format(label))
        elif (project is not None) and (session is not None):
            self.parent.diwa_state.send_print_to_status('Event: ' + label)
            wx.CallAfter(self.parent.diwa_state.worker.create_event, label)
        wx.CallLater(1000, self.HideNow)
        if event:
            event.Skip()

    def CheckVisibility(self, selection):
        """
        Checks the visibility.

        """
        sel_correct = (selection == self.selection_made)
        if sel_correct and self.IsShown() and not self.on_text:
            self.HideNow()


class GraphicalUserInterface(GUItemplate):
    """
    WOS Application Frame.

    """
    def __init__(self):
        # SUPER #
        kwargs = {
            'parent': None,
            'title': diwavars.TRAY_TOOLTIP,
            'size': diwavars.FRAME_SIZE,
            'style': wx.FRAME_NO_TASKBAR
        }
        GUItemplate.__init__(self, **kwargs)

        # UI can not be shown yet.
        self.Hide()
        self.Freeze()
        NodeScreen.update_bitmaps()
        profiles = ChooseDiwaProfileDialog.ListDatabaseProfiles()
        if len(profiles):
            params = {'profiles': profiles}
            ret = show_modal_and_destroy(ChooseDiwaProfileDialog, None, params)
            if ret:  # If non-zero return value, we should exit
                LOGGER.info('Application closed!')
                self.Destroy()
                wx.GetApp().ExitMainLoop()
                return

        # List for choices
        LOGGER.debug('WxPython version {0!s}'.format(wx.version()))
        self.list = EventList(self)
        self.splash_screen = MySplashScreen()
        self.splash_screen.Show()
        self.screen_selected = None
        self.ui_initialized = False
        self.diwa_state = state.State(parent=self)
        self.InitUICore()
        self.diwa_state.initialize()
        pub.sendMessage('update_screens', update=True)
        if self.diwa_state.config_was_created:
            self.OnPreferences(None)

        # UI can be shown now.
        self.Thaw()
        self.Show()

        # Perform initial testing before actual initialization.
        initial_test = state.initialization_test()
        if initial_test:
            self.splash_screen.Hide()
            self.splash_screen.Destroy()
            if initial_test:
                params = {'message': initial_test}
                show_modal_and_destroy(ErrorDialog, self, params)
            self.Destroy()
            wx.GetApp().ExitMainLoop()
            return
        diwavars.set_default_cursor(self.GetCursor())
        diwavars.set_blank_cursor(wx.StockCursor(wx.CURSOR_BLANK))
        self.overlay = BlackOverlay((0, 0), wx.DisplaySize(), self, '')
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)
        try:
            self.trayicon = SysTray(self)
            self.trayicon.Bind(wx.EVT_MENU, self.OnExit, id=wx.ID_EXIT)
            self.trayicon.Bind(wx.EVT_MENU, self.OnPreferences, id=wx.ID_SETUP)
            self.trayicon.Bind(wx.EVT_MENU, self.OnSession, id=wx.ID_NEW)
            self.trayicon.Bind(wx.EVT_MENU, self.OnAboutBox, id=wx.ID_ABOUT)
            self.trayicon.Bind(wx.EVT_MENU, self.SelectProjectDialog,
                               id=wx.ID_VIEW_LIST)
            self.Bind(wx.EVT_CLOSE, self.OnExit)
            self.trayicon.Bind(wx.EVT_MENU, self.OpenProjectDir,
                               id=wx.ID_INDEX)
            self.icon = wx.Icon(diwavars.TRAY_ICON, wx.BITMAP_TYPE_PNG)
            self.trayicon.SetIcon(self.icon, diwavars.TRAY_TOOLTIP)
            wx.EVT_TASKBAR_LEFT_UP(self.trayicon, self.OnTaskBarActivate)
            self.Refresh()
            self.Show(True)
            self.splash_screen.Hide()
            self.splash_screen.Destroy()
        except Exception as excp:
            LOGGER.exception('load exception: {0!s}'.format(excp))
            self.splash_screen.Hide()
            self.splash_screen.Destroy()
            self.Destroy()

    def InitUICore(self):
        """
        Inits the Core UI (:py:meth:`guitemplates.GUItemplate.InitUI`) and
        binds the functionality.

        """
        if self.ui_initialized:
            return
        self.InitUI(self.diwa_state.swnp.node.id)
        self.probtn.Bind(wx.EVT_BUTTON, self.SelectProjectDialog)
        self.dirbtn.Bind(wx.EVT_BUTTON, self.OpenProjectDir)
        self.sesbtn.Bind(wx.EVT_BUTTON, self.OnSession)
        self.setbtn.Bind(wx.EVT_BUTTON, self.OnPreferences)
        self.hidebtn.Bind(wx.EVT_BUTTON, self.OnTaskBarActivate)
        self.closebtn.Bind(wx.EVT_BUTTON, self.OnExit)
        self.evtbtn.Bind(wx.EVT_BUTTON, self.OnEventButton)
        self.logo.Bind(wx.EVT_LEFT_DOWN, self.OnAboutBox)
        self.diwawabtn.Bind(wx.EVT_BUTTON, self.OnWABtn)
        self.diwambbtn.Bind(wx.EVT_BUTTON, self.OnMBBtn)
        self.infobtn.Bind(wx.EVT_BUTTON, self.OnInfoBtn)
        self.left.Bind(wx.EVT_BUTTON, self.Shift)
        self.right.Bind(wx.EVT_BUTTON, self.Shift)
        pub.subscribe(self.UpdateScreens, 'update_screens')
        pub.subscribe(self.diwa_state.message_handler, 'message_received')
        pub.subscribe(self.ConnectionErrorHandler, 'ConnectionErrorHandler')
        self.ui_initialized = True

    def OnPreferences(self, event):
        """
        Preferences dialog event handler.

        :param event: GraphicalUserInterface Event.
        :type event: Event

        """
        params = {'config_object': diwavars.CONFIG}
        show_modal_and_destroy(PreferencesDialog, self, params)
        try:
            # Inform other nodes of new name/screen setting and update
            # your own screen if need be.
            should_update = False
            node_manager = self.diwa_state.swnp
            screens = 0
            if 'SCREENS' in diwavars.CONFIG:
                screens = int(diwavars.CONFIG['SCREENS'])
            name = 'DEFAULT_NAME'
            if 'NAME' in diwavars.CONFIG:
                name = diwavars.CONFIG['NAME']
            if 'STATUS_BOX' in diwavars.CONFIG:
                status_box = literal_eval(diwavars.CONFIG['STATUS_BOX'])
                diwavars.update_status_box(status_box)
            if node_manager.node.screens != screens:
                node_manager.set_screens(screens)
                should_update = True
            if node_manager.node.name != name:
                node_manager.set_name(name)
                should_update = True
            if should_update:
                pub.sendMessage('update_screens', update=True)
        except (ValueError, IOError, OSError):  # TODO: More?
            LOGGER.exception('Show prefs exception.')
        if event:
            event.Skip()

    def OnFocus(self, event):
        """
        Event handler for gained focus.

        :param event: GUI event.
        :type event: :py:class:`wx.Event`

        """
        self.list.Hide()
        if event:
            event.Skip()

    def OpenProjectDir(self, event):
        """
        Opens project directory in windows explorer.

        :param event: The GraphicalUserInterface event.
        :type event: Event

        """
        project_id = self.diwa_state.current_project_id
        if project_id < 1:
            return
        file_path = unicode(Project.get_by_id(project_id).dir)
        if file_path:
            os.startfile(file_path, u'explore')
        else:
            log_msg = u'Failed explorer: {0}'
            log_msg = log_msg.format(file_path)
            LOGGER.exception(log_msg.encode('utf-8'))  # FIXME
            params = {'message': 'Could not open directory.'}
            show_modal_and_destroy(ErrorDialog, self, params)
        if event:
            event.Skip()

    def EnableSessionButton(self):
        """
        Used to enable the needed buttons after session has been started.

        """
        self.sesbtn.SetBitmapLabel(self.GetProgramIcon('session_on'))
        self.sesbtn.Enable()
        self.evtbtn.Enable()
        self.sesbtn.Refresh()
        self.evtbtn.Refresh()
        self.sesbtn.Update()
        self.evtbtn.Update()
        self.evtbtn.SetFocus()

    def DisableSessionButton(self):
        """
        Used to disable the needed buttons after session has been stopped.

        .. note::
            Does not actually disable to session button, only the session
            state of the button.

        """
        self.sesbtn.SetBitmapLabel(self.GetProgramIcon('session_off'))
        self.evtbtn.Disable()
        self.sesbtn.Refresh()
        self.evtbtn.Refresh()
        self.sesbtn.Update()
        self.evtbtn.Update()

    def EnableDirectoryButton(self):
        """
        Used to enable the project directory button when project has been
        selected.

        """
        self.dirbtn.Enable()
        self.dirbtn.Refresh()
        self.dirbtn.Update()

    def DisableDirectoryButton(self):
        """
        Used to disable the project directory button when project has been
        unselected.

        .. note::
            There should be no need for this as the software should
            always start a new project after the old one ends.
            But for the mid state to be legitimate this is still
            usable.

        """
        self.dirbtn.Disable()
        self.dirbtn.Refresh()
        self.dirbtn.Update()

    def SetProjectName(self, name):
        """
        Set the project text.
        For example "No Project Selection".

        .. note::
            Requires None explicitly when the purpose is to set default label
            because writing SetProjectName(None) is more informative than
            SetProjectName()

        :param name: The name of the project to set as label.
        :type name: String

        """
        if name is None:
            name = u'No Project Selection'
        self.pro_label.SetLabel(u'Project: {0}'.format(name))

    def SelectProjectDialog(self, event):
        """
        Select project event handler.

        :param event: GraphicalUserInterface Event.
        :type event: Event

        """
        if self.diwa_state.current_session:
            msg = 'Cannot change project during session.'
            show_modal_and_destroy(ErrorDialog, self, {'message': msg})
            return
        show_modal_and_destroy(ProjectSelectDialog, self)
        if event:
            event.Skip()

    def OnWABtn(self, event):
        """
        Handles the pressing of Web-application button.

        Directs the user to web-storage website.

        """
        webbrowser.open('http://' + diwavars.STORAGE + '/')
        if event:
            event.Skip()

    def OnMBBtn(self, event):
        """
        Handles the pressing of meetings browser button.

        Directs the user to web-storage website/mb.

        """
        webbrowser.open('http://' + diwavars.STORAGE + '/mb/')
        if event:
            event.Skip()

    def OnInfoBtn(self, event):
        """
        Handles the pressing of Web-information button.

        Directs the user to web-storage website/help.

        """
        webbrowser.open('http://' + diwavars.STORAGE + '/help/')
        if event:
            event.Skip()

    def OnEventButton(self, event):
        """
        Event Button handler.

        :param event: GraphicalUserInterface Event.
        :type event: Event

        """
        # create default event
        self.list.SetFocus()
        self.list.ShowNow()
        if event:
            event.Skip()

    #=====================================================================
    #    def CustomEventMenu(self, event):
    #        event.Skip()
    #        title = self.event_menu_title_by_id[event.GetId()]
    #        if not self.is_responsive:
    #            self.SwnpSend(self.responsive, "event;" + title)
    #        elif self.current_project_id and self.current_session_id:
    #            wx.CallAfter(diwavars.WINDOW_TAIL * 1000,
    #                         self.worker.create_event, title)
    #=====================================================================

    def Shift(self, event):
        """
        Caroussel Shift function.

        :param event: GraphicalUserInterface Event.
        :type event: Event

        """
        def limit_int(min_value, value, max_value):
            """
            Limit the value between values of [min_value, max_value].

            """
            return min(max(value, min_value), max_value)

        if len(self.nodes) > 3:
            if event.GetId() == wx.ID_BACKWARD:
                new_iterator = self.iterator - 1
            elif event.GetId() == wx.ID_FORWARD:
                new_iterator = self.iterator + 1
            max_value = max(len(self.nodes) - 3, 0)
            self.iterator = limit_int(0, new_iterator, max_value)
            pub.sendMessage('update_screens', update=True)

    def OnProjectChanged(self):
        """
        Project selected event handler.

        """
        project = self.diwa_state.current_project
        session = self.diwa_state.current_session
        caller = inspect.stack()[1][3]
        if project is not None:
            self.diwa_state.on_project_selected()
            self.SetProjectName(project.name)
            self.EnableDirectoryButton()
            self.sesbtn.Enable(True)
            if caller == 'OnProjectSelect':
                msg = 'Project: {0}'.format(project.name)
                self.diwa_state.send_print_to_status(msg)
        else:
            self.SetProjectName(None)
            self.DisableDirectoryButton()
        if session is not None:
            self.EnableSessionButton()
        else:
            self.DisableSessionButton()
        self.Refresh()
        self.Update()

    def OnSession(self, event):
        """
        Session button pressed.

        The user either desires to start a new session or end
        an existing one.

        :param event: GraphicalUserInterface Event.
        :type event: Event

        """
        session_id = self.diwa_state.current_session_id
        project_id = self.diwa_state.current_project_id
        if project_id < 1:
            # We should not ever get here as the button should be disabled!
            params = {'message': 'No project selected.'}
            show_modal_and_destroy(ErrorDialog, self, params)
        elif session_id < 1:
            # We want to start a new session!
            try:
                self.diwa_state.on_session_changed(True)
                self.EnableSessionButton()
                session_id = self.diwa_state.current_session_id
                msg = 'Session started: {0}'.format(session_id)
                LOGGER.info(msg)
            except state.SessionChangeException:
                params = {'message': 'Failed to start a new session!'}
                LOGGER.exception('Session change failed...')
                show_modal_and_destroy(ErrorDialog, self, params)
            except Exception as excp:
                LOGGER.exception('OnSession exception: {0!s}'.format(excp))
        else:
            # We want to end our session!
            try:
                self.diwa_state.on_session_changed(False)
                self.DisableSessionButton()
                LOGGER.info('Session ended.')
            except Exception as excp:
                LOGGER.exception('OnSession exception: {0!s}'.format(excp))
            # TODO: Check all wx.ICON_INFORMATION uses and maybe
            #       create a common dialog for it.
            params = {
                'message': 'Session ended!',
                'caption': 'Information',
                'style': wx.OK | wx.ICON_INFORMATION
            }
            show_modal_and_destroy(wx.MessageDialog, self, params)
        self.panel.SetFocus()
        self.Refresh()
        self.Update()
        if event:
            event.Skip()

    def SelectNode(self, event):
        """
        Handles the selection of a node, start remote control.

        .. note:: For future use.

        :param event: GraphicalUserInterface Event
        :type event: Event

        """
        screen = event.GetEventObject()
        node = screen.node
        if not node:
            return
        node_manager = self.diwa_state.swnp
        sender = self.diwa_state.swnp_send
        if node.id == node_manager.node.id:
            controlled = self.diwa_state.controlled
            own_id = str(node_manager.node.id)
            for target in [str(id_) for id_ in controlled]:
                try:
                    sender(own_id, 'remote_end;{0}'.format(target))
                    sender(target, 'remote_end;{0}'.format(own_id))
                except (IOError, OSError) as excp:
                    LOGGER.exception('EXCPT! {0!s}'.format(excp))
            return
        threads.inputcapture.set_capture(True)
        try:
            # Start remote
            self.diwa_state.controlling = node.id
            self.diwa_state.capture_thread.hook()
            msg = 'remote_start;{0}'.format(node_manager.node.id)
            sender(node.id, msg)
            # Sync clipboard.
            self.diwa_state.send_push_clipboard(node.id)
            if node.id not in self.selected_nodes:
                self.selected_nodes.append(node.id)
            self.Refresh()
            tmod = pyHook.HookConstants.IDToName(diwavars.KEY_MODIFIER)
            tkey = pyHook.HookConstants.IDToName(diwavars.KEY)
            self.overlay.SetText(tmod, tkey)
            self.overlay.Show()
        except (IOError, OSError) as excp:
            LOGGER.exception('EXCPT! {0!s}'.format(excp))

    def UpdateScreens(self, update):
        """
        Called when screens need to be updated and redrawn.

        :param update: Pubsub needs one param, therefore it is called update.
        :type update: Boolean

        """
        update = update  # Intentionally left unused.
        if not self.init_screens_done:
            return
        self.Freeze()  # Prevents flickering.
        # self.HideScreens()
        self.nodes = self.diwa_state.swnp.get_screen_list()
        arrows_should_be_enabled = len(self.nodes) > 3
        for arrow in [self.left, self.right]:
            if arrows_should_be_enabled:
                if not arrow.IsShown():
                    arrow.Show()
                    arrow.Refresh()
            else:
                if arrow.IsShown():
                    arrow.Hide()
                    arrow.Refresh()
        for i in xrange(0, min(diwavars.MAX_SCREENS, len(self.nodes))):
            iterated = (i + self.iterator) % len(self.nodes)
            node_screen = self.node_screens[i]
            node_screen.Enable()
            # TODO: When reloading, remove old registry entry.
            node_screen.ReloadAs(self.nodes[iterated])
        if len(self.nodes) < diwavars.MAX_SCREENS:
            for i in xrange(len(self.nodes), diwavars.MAX_SCREENS):
                self.node_screens[i].EmptyScreen()
                self.node_screens[i].Disable()
                # TODO: Remove old registry entry.
        for node in self.nodes:
            try:
                self.diwa_state.worker.add_registry_entry(node.name, node.id)
            except WindowsError:
                pass
        self.diwa_state.worker.check_responsive()
        self.Thaw()  # Pair for freeze()

    def OnExit(self, event):
        """
        Exits program.

        :param event: GraphicalUserInterface Event
        :type event: Event

        """
        if event and isinstance(event, threads.ContextMenuFailure):
            error_text = (
                'Socket binding error. You might have multiple instances of '
                'the software running.\n'
                'Please wait for them to terminate or use the task manager '
                'to force all of them to quit.\n\n'
                'Press OK to start waiting...'
            )
            params = {'message': error_text}
            show_modal_and_destroy(ErrorDialog, self, params)
        if not self.exited:
            try:
                self.exited = True
                self.overlay.Destroy()
                self.Hide()
                self.trayicon.RemoveIcon()
                self.trayicon.Destroy()
                self.trayicon = None
                self.closebtn.SetToolTip(None)
                if not event == 'conn_err' and self.diwa_state.is_responsive:
                    LOGGER.debug('On exit self is responsive')
                    self.diwa_state.remove_observer()
                last_computer = controller.last_active_computer()
                if not event == 'conn_err' and last_computer:
                    LOGGER.debug('On exit self is last active computer.')
                    controller.unset_activity(diwavars.PGM_GROUP)
                    session_id = self.diwa_state.current_session_id
                    if session_id:
                        controller.end_session(session_id)
                LOGGER.debug('Application closing...')
                utils.MapNetworkShare('W:')
                diwavars.update_responsive(0)
                sleep(0.5)
                self.diwa_state.destroy()
                LOGGER.debug('GraphicalUserInterface closing...')
                self.Destroy()
                LOGGER.info('Application closed!')
                wx.GetApp().ExitMainLoop()
            except CloseError:
                raise  # Raise without parameter rises the original exception.
                        # This also preseves the original traceback.
            except Exception as excp:
                LOGGER.exception('Exception in Close: {0!s}'.format(excp))
                for thread in threading.enumerate():
                    LOGGER.debug(thread.getName())
                self.Destroy()
                wx.GetApp().ExitMainLoop()

    def OnAboutBox(self, event):
        """
        About dialog.

        :param event: GraphicalUserInterface Event.
        :type event: Event

        """
        description = (diwavars.APPLICATION_NAME +
            ' is the windows client for DiWa - A distributed meeting room '
            'collaboration system.\n\n'
            'Lead programmer: Nick Eriksson\n'
            'Contributors: Mika P. Nieminen, Mikael Runonen, Mari Tyllinen, '
            'Vikki du Preez, Marko Nieminen'
        )
        copyright_text = ('(c) 2012-2013 DiWa project by Strategic Usability '
                          'Research Group STRATUS, Aalto University School of '
                          'Science.')

        unused_licence = """
        DiwaCS is free software.
        """
        info = wx.AboutDialogInfo()
        iconpath = os.path.join('data', 'splashscreen.png')
        icon = wx.Icon(iconpath, wx.BITMAP_TYPE_PNG)
        info.SetIcon(icon)
        info.SetName(diwavars.APPLICATION_NAME)
        info.SetVersion(diwavars.VERSION)
        info.SetDescription(description)
        info.SetCopyright(copyright_text)
        info.SetWebSite('http://stratus.soberit.hut.fi/')
        wx.AboutBox(info)
        if event:
            event.Skip()

    def OnIconify(self, event):
        """
        Window minimize event handler.
        Should toggle the minimized state of the application.

        :param evt: GraphicalUserInterface Event.
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
        if event:
            event.Skip()

    def OnTaskBarActivate(self, event):
        """
        Taskbar activate event handler.

        :param event: GraphicalUserInterface Event.
        :type event: Event

        """
        if self.IsIconized():
            # The user wants to unminimize the application.
            self.Show()
            self.Raise()
            self.SetFocus()
            self.Iconize(False)
            self.Refresh()
        else:
            # The user wants to minimize the application.
            self.Hide()
            self.Iconize(True)
        if event:
            event.Skip()

    def OnTaskBarClose(self, unused_event):
        """
        Taskbar close event handler.

        :param evt: GraphicalUserInterface Event.
        :type evt: Event

        """
        wx.CallAfter(self.Close)


def main(profile):
    """
    Main function.

    :warning:
        The profiler has been pre-calibrated using the development machine
        so this should be changed for other development environments that
        wish to profile the execution of the diwacs system.

        THIS ONLY WORKS WHEN diwavars.DEBUG HAS BEEN ENABLED.

        Remember to disable it from release binaries.

    :param profile: should the call be profiled?
    :type profile: Boolean

    """
    profiler = None
    if profile:
        profiler = cProfile.Profile()
        profiler.bias = 7.6e-7  # Note: This is system dependent.
                                #       Please calibrate yourself.
        profiler.enable(subcalls=True, builtins=False)
    LOGGER.info('\n\n\n')
    LOGGER.info('Application started')
    app = wx.App()
    window = None
    try:
        window = GraphicalUserInterface()
        app.MainLoop()
    except Exception as excp:
        LOGGER.exception('GENERIC EXCEPTION: {0!s}'.format(excp))
    finally:
        if window:
            window = None
        app.Destroy()
    if profile:
        profiler.disable()
        LOGGER.info('PROFILING PRINT BEGIN...')
        try:
            output_buffer = StringIO.StringIO()
            stater = pstats.Stats(profiler, stream=output_buffer)
            stater.sort_stats('nfl')
            stater.print_stats()
            output_buffer.flush()
            sval = output_buffer.getvalue()
            output_buffer.close()
            suffix = str(datetime.datetime.now())
            suffix = suffix.replace('-', '')
            suffix = suffix.replace(':', '')
            suffix = suffix.replace(' ', '_')
            rindex = suffix.rfind('.')
            if rindex > 0:
                suffix = suffix[:rindex]
            log_path = r'data\diwacs_profile_{0}.log'.format(suffix)
            with open(log_path, 'w') as ofile:
                ofile.write('PROFILE DATA:\n\n')
                ofile.write(sval)
        except (ValueError, IOError, OSError) as excp:
            LOGGER.exception('PROFILING EXCEPTION: {0!s}'.format(excp))
        LOGGER.info('...PROFILING PRINT END')


if __name__ == '__main__':
    if diwavars.DEBUG:
        main(profile=('profile' in sys.argv))
    else:
        main(profile=False)
