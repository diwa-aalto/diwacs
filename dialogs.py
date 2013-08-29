"""
Created on 4.6.2013

:platform: Windows Vista, Windows 7, Windows 8
:synopsis: Define the pop-up dialogs for the application.
:note: Requires WxPython.
:author: neriksso

"""
# System imports
from logging import config, getLogger
import re
import webbrowser
import os

# Third party imports
import wx
from configobj import ConfigObj

# Own imports
import controller
import diwavars
from models import Company, Project
import filesystem
import modelsbase

LOGGER = None
_NAMES = (
    u'CON', u'PRN', u'AUX', u'NUL', u'CC', u'LP', u'COM[0-9]', u'LPT[0-9]'
)
_PATTERNS = ['^{0}(\\.[^\\.]+)?$'.format(name) for name in _NAMES]
FORBIDDEN_FOLDERNAMES = [re.compile(pattern) for pattern in _PATTERNS]
FORBIDDEN_CHARACTERS = (u'/', u'\\', u'<', u'>', u':', u'"', u'|', u'?', u'*')

# "Too many" public method (because wxPython 'derived'-classes are inherited).
# pylint: disable=R0904


def __init_logger():
    """
    Used to initialize the logger, when running from diwacs.py

    """
    global LOGGER
    config.fileConfig('logging.conf')
    LOGGER = getLogger('dialogs')


def __set_logger_level(level):
    """
    Sets the logger level for dialogs logger.

    :param level: Level of logging.
    :type level: Integer

    """
    LOGGER.setLevel(level)


diwavars.add_logger_initializer(__init_logger)
diwavars.add_logger_level_setter(__set_logger_level)


def show_modal_and_destroy(class_, parent, params=None):
    """
    Used to show modal and destroy afterwards.

    .. note::
        The implementation is kind of ugly, but guarantees a safe execution
        of the dialog without memory leaks and with all exceptions logged.

    :param class_: The type of dialog to show.
    :type class_: type

    :param parent: The parent wx.Window of this object.
    :type parent: :py:class:`wx.Window`

    :param params: The params to give for __init__ call.
    :type params: Dictionary.

    :returns: The modal result value.
    :rtype: Integer

    """
    dialog = None
    result = None
    try:
        if params:
            dialog = class_(parent, **params)
        else:
            dialog = class_(parent)
        result = dialog.ShowModal()
    except Exception as excp:
        LOGGER.exception('Exception in {0!s}: {1!s}'.format(class_, excp))
    finally:
        try:
            dialog.Destroy()
        except (NameError, AttributeError):
            pass
    dialog = None
    return result


class AddProjectDialog(wx.Dialog):
    """
    A dialog for adding a new project

    :param parent: Parent frame.
    :type parent: :class:`wx.Frame`

    :param title: A title for the dialog.
    :type title: String

     """
    def __init__(self, parent, title, project_id=None):
        wx.Dialog.__init__(self, parent, title=title,
                           style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
                           size=(250, 200))
        self.project_id = 0
        self.parent = parent

        to_print = {
            'parent': parent,
            'title': title,
            'project_id': project_id
        }
        msg = ['AddProjectDebug:\n']
        for key in to_print:
            msg.append('{0}={1}'.format(key, to_print[key]))
        LOGGER.debug(''.join(msg))

        # Static definitions of common strings.
        add_label = 'Create'
        cancel_label = 'Cancel'
        name_label_text = 'Project Name'
        dir_label_text = 'Project Folder Name (optional):'
        password_label_text = 'Project Password (optional):'

        # If there is already an project on way.
        if project_id:
            self.project_id = project_id
            add_label = 'Save'
            dir_label_text = 'Project Folder Path'

        # Initialize the child elements.
        name_label = wx.StaticText(self, label=name_label_text)
        dir_label = wx.StaticText(self, label=dir_label_text)
        password_label = wx.StaticText(self, label=password_label_text)
        self.name = wx.TextCtrl(self, wx.ID_ANY)
        self.dir = wx.TextCtrl(self, wx.ID_ANY)
        self.password = wx.TextCtrl(self, wx.ID_ANY, style=wx.TE_PASSWORD)
        ok_button = wx.Button(self, label=add_label)
        close_button = wx.Button(self, label=cancel_label)

        # Add elements that should be displayed vertically.
        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(name_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        vbox.Add(self.name, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        vbox.Add(dir_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        vbox.Add(self.dir, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        vbox.Add(password_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        vbox.Add(self.password, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

        # Add elements that should be displayed horizontally.
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(ok_button)
        hbox.Add(close_button, flag=wx.LEFT, border=5)

        # The project handling.
        if self.project_id:
            project = Project.get_by_id(project_id)
            self.name.SetValue(project.name)
            self.dir.SetValue(project.dir)

        # Finalize the layout.
        vbox.Add(hbox, flag=wx.ALIGN_CENTER, border=0)
        self.SetSizer(vbox)
        vbox.Fit(self)

        # Bind actions.
        ok_button.Bind(wx.EVT_BUTTON, self.OnAdd)
        close_button.Bind(wx.EVT_BUTTON, self.OnClose)
        self.dir.Bind(wx.EVT_TEXT, self.OnText)
        self.password.Bind(wx.EVT_TEXT, self.OnText)

    def OnAdd(self, event):
        """
        Handles the addition of a project to database, when "Add" button
        is pressed.

        :param event: GUI Event.
        :type event: Event

        """
        result = None
        if self.name.GetValue() == '':  # or not self.passw.GetValue():
            msg = 'Please fill all necessary fields'
            show_modal_and_destroy(ErrorDialog, self, {'message': msg})
            if event:
                event.Skip()
            return
        if not self._IsValidPath(self.dir.GetValue()):
            msg = ('The folder name you specified is not valid for Microsoft '
                   'Windows operating system for the given purpose.')
            show_modal_and_destroy(ErrorDialog, self, {'message': msg})
            if event:
                event.Skip()
                return
        try:
            company = Company.get_by_id()
            project_data = {
                'name': self.name.GetValue(),
                'dir': self.dir.GetValue(),
                'password': self.password.GetValue()
            }
            company_data = {
                'name': company.name
            }
            data = {
                'project': project_data,
                'company': company_data
            }
            if not self.dir.GetValue():
                project_data.pop('dir')
            project = controller.add_project(data)
            LOGGER.info('Created Project {0.name} (id={0.id})'.format(project))
            result = project.id
        except Exception as excp:
            LOGGER.exception('Error in add project: {0!s}'.format(excp))
            self.EndModal(-1)
            return

        if not result:
            LOGGER.exception('ERROR in add project!')
            self.EndModal(-1)
            return
        try:
            if result != self.parent.diwa_state.current_project_id:
                self.parent.diwa_state.set_current_project(project.id)
                self.parent.diwa_state.start_current_project_thread()
                self.parent.OnProjectChanged()
                LOGGER.debug('Current Project set')
                params = {'project_id': result}
                dlg_result = show_modal_and_destroy(ProjectSelectedDialog,
                                                    self, params)
                if dlg_result == wx.ID_NO:
                    self.parent.OnSession(None)
        except Exception as excp:
            log_msg = 'Exception in Project creation: {0!s}'
            LOGGER.exception(log_msg.format(excp))
        self.EndModal(result)

    @staticmethod
    def _IsValidPath(path):
        for character in path:
            if character in FORBIDDEN_CHARACTERS:
                return False
        for forbidden in FORBIDDEN_FOLDERNAMES:
            if forbidden.match(path):
                return False
        # Should actually be return "Maybe" but _some_ checking is better
        # than no checking at all.
        return True

    def OnText(self, event):
        """
        Event handler for text changed.

        """
        source_object = event.GetEventObject()
        source_string = source_object.GetValue()
        if source_object == self.dir:
            self.password.SetEditable(len(source_string) == 0)
            color = 'red'
            if self._IsValidPath(self.dir.GetValue()):
                color = 'default'
            self.dir.SetBackgroundColour(color)
            self.dir.Refresh()
            self.dir.Update()
            event.Skip(len(self.password.GetValue()) > 0)
        else:
            self.dir.SetEditable(len(source_string) == 0)
            event.Skip(len(self.dir.GetValue()) > 0)

    def OnClose(self, event):
        """
        Handles "Close" button presses.

        :param event: GUI Event.
        :type event: Event

        """
        if event:
            event.Skip(False)
        self.EndModal(0)


class CloseError(Exception):
    """
    Class describing an error while closing application.

    """
    def __init__(self, *args, **kwds):
        Exception.__init__(self, *args, **kwds)

    def __str__(self):
        """
        Returns a string representation of CloseError.

        """
        return 'CloseError'

    def __unicode__(self):
        """
        Returns a string representation (Unicode variant) of CloseError.

        """
        return u'CloseError'


class ConnectionErrorDialog(wx.ProgressDialog):
    """
    Create a connection error dialog that informs the user about reconnection
    attempts made by the software.

    """
    stat_text = ('Reconnecting... DiWaCS will shutdown in {0} seconds if '
                 'no connection is made.')
    imax = 80

    def __init__(self, parent):
        self.parent = parent
        wx.ProgressDialog.__init__(self, 'Connection Error',
                                   ConnectionErrorDialog.stat_text.format(20),
                                   maximum=ConnectionErrorDialog.imax,
                                   parent=self.parent,
                                   style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)

    def GetResult(self):
        """
        Try to reconnect and return the outcome.

        """
        success = False
        count = 0
        while not success and count < ConnectionErrorDialog.imax:
            count += 1
            wx.MilliSleep(250)
            tests = [filesystem.test_storage_connection(),
                     controller.test_connection()]
            success = True
            for test in tests:
                if not test:
                    success = False
                    break
            if count % 4 == 0:
                seconds = (ConnectionErrorDialog.imax - count) / 4
                notice = ConnectionErrorDialog.stat_text.format(seconds)
                self.Update(count, notice)
        return not success


class DeleteProjectDialog(wx.Dialog):
    """
    A dialog for deleting project.

    """
    def __init__(self, parent, title, project_id):
        wx.Dialog.__init__(self, parent=parent, title=title,
                           style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
                           size=(250, 200))
        self.project = Project.get_by_id(project_id)
        if not self.project:
            self.Destroy()
            msg = 'The project does not seem to exist anymore.'
            show_modal_and_destroy(ErrorDialog, parent, {'message': msg})
            return

        label_text = ('You are about to delete project "{0}" permanently. '
                      ' Are you really sure?')
        label_text = label_text.format(self.project.name)
        self.notice = wx.StaticText(self, label=label_text)
        yes_text = 'Yes, delete the project.'
        files_text = 'Also delete all saved project files.'
        self.yes_delete = wx.CheckBox(self, wx.ID_ANY, yes_text)
        self.files_delete = wx.CheckBox(self, wx.ID_ANY, files_text)
        self.ok_button = wx.Button(self, wx.ID_ANY, 'OK')
        self.cancel_button = wx.Button(self, wx.ID_ANY, 'Cancel')
        self.ok_button.Bind(wx.EVT_BUTTON, self.OnOk)
        self.cancel_button.Bind(wx.EVT_BUTTON, self.OnCancel)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.Add(self.ok_button, 0)
        button_sizer.Add(self.cancel_button, 0)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.notice, 0, wx.ALL, 5)
        sizer.Add(self.yes_delete, 0, wx.ALL, 5)
        sizer.Add(self.files_delete, 0, wx.ALL, 5)
        sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        self.SetSizerAndFit(sizer)
        self.SetFocus()

    def OnOk(self, event):
        """
        Event handler for pressing OK button.

        """
        if event:
            event.Skip(False)
        ret = 0
        if self.yes_delete.GetValue():
            ret += 1
        if self.files_delete.GetValue():
            ret += 2
        self.EndModal(ret)

    def OnCancel(self, event):
        """
        Event handler for pressing Cancel button.

        """
        if event:
            event.Skip(False)
        self.EndModal(0)


class ErrorDialog(wx.MessageDialog):
    """
    Error dialog.

    """
    def __init__(self, parent, message):
        wx.MessageDialog.__init__(self,
                                  parent=parent,
                                  message=message,
                                  caption='Error',
                                  style=wx.OK | wx.ICON_ERROR)


class PreferencesDialog(wx.Dialog):
    """
    Creates and displays a preferences dialog that allows the user to
    change some settings.

    :param config_object: a Config object
    :type config_object: :py:class:`configobj.ConfigObj`

    """

    #----------------------------------------------------------------------
    def __init__(self, parent, config_object):
        wx.Dialog.__init__(self,
                           parent=parent,
                           id=wx.ID_ANY,
                           title='Preferences',
                           size=(550, 300),
                           style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
        self.config = config_object
        self.parent = parent

        # Labels.
        screens_label = wx.StaticText(self, wx.ID_ANY, 'Screen visibility:')
        commands_label = wx.StaticText(self, wx.ID_ANY, 'Run commands:')
        responsive_label = wx.StaticText(self, wx.ID_ANY, 'Act as Responsive:')
        name_label = wx.StaticText(self, wx.ID_ANY, 'Name:')
        pgm_group_dropdown_label = wx.StaticText(self, wx.ID_ANY,
                                                 'Edit PGM_GROUP:')

        # Configuration controls.
        self.screens_hidden = wx.RadioButton(self, wx.ID_ANY,
                                             'Off (recommended)',
                                             style=wx.RB_GROUP)
        self.screens_show = wx.RadioButton(self, wx.ID_ANY, 'On')
        self.commands_on = wx.RadioButton(self, wx.ID_ANY, 'On',
                                          style=wx.RB_GROUP)
        self.commands_off = wx.RadioButton(self, wx.ID_ANY,
                                           'Off  (recommended)')
        self.responsive_on = wx.RadioButton(self, wx.ID_ANY, 'On',
                                          style=wx.RB_GROUP)
        self.responsive_off = wx.RadioButton(self, wx.ID_ANY,
                                           'Off  (recommended)')
        self.name_value = wx.TextCtrl(self, wx.ID_ANY, '')

        # Tooltips.
        txt_screens_off = ('This setting hides your computer from others, '
                           'but you are still able to send files etc to '
                           'other screens and control them.')
        txt_screens_on = ('This setting makes your computer visible to '
                          'others, so others can send files etc to it and '
                          'control it.')
        txt_commands_off = ('This will disable the server from sending '
                            'remote commands like "shutdown" to your '
                            'computer.')
        txt_commands_on = ('This will enable the server to send remote '
                           'commands like "shutdown" to your computer.')
        txt_responsive_off = ('This is the basic setting for a regular'
                              ' peer node.')
        txt_responsive_on = ('This setting makes it possible for this client'
                             ' to act as a responsive node which has'
                             ' responsibilities such as monitoring file '
                             'system and recording audio. This should be only'
                             ' enabled for stationary nodes.')
        txt_pgm_group = ('This allows you to set the PGM_GROUP.')
        self.screens_hidden.SetToolTip(wx.ToolTip(txt_screens_off))
        self.screens_show.SetToolTip(wx.ToolTip(txt_screens_on))
        self.commands_off.SetToolTip(wx.ToolTip(txt_commands_off))
        self.commands_on.SetToolTip(wx.ToolTip(txt_commands_on))
        self.responsive_off.SetToolTip(wx.ToolTip(txt_responsive_off))
        self.responsive_on.SetToolTip(wx.ToolTip(txt_responsive_on))

        # Other controls.
        open_button = wx.Button(self, wx.ID_ANY, 'Config File')
        open_button.Bind(wx.EVT_BUTTON, self.OpenConfig)
        reload_button = wx.Button(self, wx.ID_ANY, 'Reload Config File')
        reload_button.Bind(wx.EVT_BUTTON, self.ReloadConfig)
        save_button = wx.Button(self, wx.ID_ANY, 'OK')
        save_button.Bind(wx.EVT_BUTTON, self.SavePreferences)
        cancel_button = wx.Button(self, wx.ID_ANY, 'Cancel')
        cancel_button.Bind(wx.EVT_BUTTON, self.OnCancel)
        box = wx.ComboBox(self, wx.ID_ANY,
                          choices=[str(x) for x in range(1, 10)],
                          style=wx.CB_DROPDOWN | wx.CB_READONLY | wx.CB_SORT)
        box.SetMinSize((200, box.GetMinHeight()))
        self.pgm_group_dropdown = box
        self.pgm_group_dropdown.SetToolTip(wx.ToolTip(txt_pgm_group))
        # Preferences sizers.
        preferences_sizer = wx.FlexGridSizer(cols=2, hgap=8, vgap=8)
        preferences_sizer.AddGrowableCol(1)
        radio_sizer_screens = wx.BoxSizer(wx.HORIZONTAL)
        radio_sizer_commands = wx.BoxSizer(wx.HORIZONTAL)
        radio_sizer_responsive = wx.BoxSizer(wx.HORIZONTAL)

        radio_sizer_screens.Add(self.screens_hidden)
        radio_sizer_screens.AddSpacer(5)
        radio_sizer_screens.Add(self.screens_show)
        radio_sizer_commands.Add(self.commands_off)
        radio_sizer_commands.AddSpacer(5)
        radio_sizer_commands.Add(self.commands_on)
        radio_sizer_responsive.Add(self.responsive_off)
        radio_sizer_responsive.AddSpacer(5)
        radio_sizer_responsive.Add(self.responsive_on)

        # Layout Preferences.
        preferences_sizer.Add(screens_label, 0,
                              wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        preferences_sizer.Add(radio_sizer_screens, 0, wx.EXPAND)

        preferences_sizer.Add(commands_label, 0,
                              wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        preferences_sizer.Add(radio_sizer_commands, 0, wx.EXPAND)

        preferences_sizer.Add(responsive_label, 0,
                              wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        preferences_sizer.Add(radio_sizer_responsive, 0, wx.EXPAND)

        preferences_sizer.Add(name_label, 0,
                              wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        preferences_sizer.Add(self.name_value, 0, wx.EXPAND)

        preferences_sizer.Add(pgm_group_dropdown_label, 0,
                              wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        preferences_sizer.Add(self.pgm_group_dropdown, 1, wx.EXPAND)

        # Layout.
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        config_button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer.Add(preferences_sizer, 0, wx.EXPAND | wx.ALL, 5)
        config_button_sizer.Add(open_button, 0, wx.ALL, 5)
        config_button_sizer.Add(reload_button, 0, wx.ALL, 5)
        main_sizer.Add(config_button_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT, 5)
        button_sizer.Add(save_button, 0, wx.ALL, 5)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)
        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.TOP, 30)
        self.SetSizerAndFit(main_sizer)

        # load preferences
        self.LoadPreferences()
        self.SetFocus()

    #---------------------------------------------------------------------
    def LoadPreferences(self):
        """
        Load the current preferences and fills the text controls.

        """
        screens = self.config['SCREENS']
        commands = self.config['RUN_CMD']
        responsive = None
        if 'RESPONSIVE' in self.config:
            responsive = self.config['RESPONSIVE']
        pgm_group = self.config['PGM_GROUP']
        name = self.config['NAME']
        LOGGER.debug('config: {0!s}'.format(self.config))
        # Screens.
        if int(screens) > 0:
            self.screens_show.SetValue(1)
            self.screens_hidden.SetValue(0)
        else:
            self.screens_show.SetValue(0)
            self.screens_hidden.SetValue(1)
        # Commands
        if int(commands) > 0:
            self.commands_on.SetValue(1)
            self.commands_off.SetValue(0)
        else:
            self.commands_on.SetValue(0)
            self.commands_off.SetValue(1)
        # Responsive
        if responsive and int(responsive) == diwavars.PGM_GROUP:
            self.responsive_on.SetValue(1)
            self.responsive_off.SetValue(0)
        else:
            self.responsive_on.SetValue(0)
            self.responsive_off.SetValue(1)
        self.pgm_group_dropdown.SetStringSelection(pgm_group)
        self.name_value.SetValue(name)

    #----------------------------------------------------------------------
    def OpenConfig(self, event):
        """
        Opens config file.

        :param event: GUI event.
        :type event: Event

        """
        if event:
            event.Skip()
        filesystem.open_file(diwavars.CONFIG_PATH)

    #----------------------------------------------------------------------
    def ReloadConfig(self, event):
        """
        Opens config file.

        :param event: GUI event.
        :type event: Event

        """
        try:
            config_loader = diwavars.CONFIG_LOADER
        except NameError:
            # Removed circular reference to state.load_config when
            # running unit tests.
            return
        diwavars.set_config(config_loader())
        self.parent.diwa_state.worker.parse_config(diwavars.CONFIG)
        self.config = diwavars.CONFIG
        self.LoadPreferences()

    #----------------------------------------------------------------------
    def OnCancel(self, event):
        """Closes the dialog without modifications.

        :param event: GUI event.
        :type event: Event

        """
        if event:
            event.Skip(False)
        self.EndModal(0)

    #----------------------------------------------------------------------
    def SavePreferences(self, event):
        """Save the preferences.

        :param event: GUI Event.
        :type event: Event

        """
        self.config['SCREENS'] = 1 if self.screens_show.GetValue() else 0
        LOGGER.debug('Screens: {0}'.format(self.config['SCREENS']))
        controller.set_node_screens(int(self.config['SCREENS']))
        self.config['RUN_CMD'] = 1 if self.commands_on.GetValue() else 0
        diwavars.set_run_cmd(self.commands_on.GetValue())
        if self.responsive_on.GetValue():
            self.config['RESPONSIVE'] = diwavars.PGM_GROUP
            diwavars.update_responsive(diwavars.PGM_GROUP)
            self.parent.diwa_state.set_responsive()
        else:
            self.config['RESPONSIVE'] = 0
            diwavars.update_responsive(0)
            self.parent.diwa_state.stop_responsive()
        self.parent.diwa_state.worker.check_responsive()
        self.config['NAME'] = self.name_value.GetValue()
        controller.set_node_name(self.config['NAME'])
        self.config.write()
        if self.config['PGM_GROUP'] != self.pgm_group_dropdown.GetValue():
            new_pgm_group = self.pgm_group_dropdown.GetValue()
            diwavars.update_pgm_group(new_pgm_group)
            diwavars.CONFIG['PGM_GROUP'] = new_pgm_group
            self.parent.diwa_state.swnp.update_pgm_group(new_pgm_group)
        params = {'message': 'Preferences Saved!',
                  'caption': 'Information',
                  'style': wx.OK | wx.ICON_INFORMATION}
        show_modal_and_destroy(wx.MessageDialog, self, params)
        if event:
            event.Skip(False)
        self.EndModal(0)


class ProjectAuthenticationDialog(wx.Dialog):
    """
    A dialog for project authentication.

    """
    def __init__(self, parent, title, project_id):
        wx.Dialog.__init__(self, parent, title=title,
                           style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
                           size=(250, 200))
        self.parent = parent
        self.project_id = project_id
        self.project = Project.get_by_id(project_id)
        label_text = 'Please enter password for Project {0}'
        label_text = label_text.format(self.project.name)
        self.notice = wx.StaticText(self, label=label_text)
        passwd_style = wx.TE_PASSWORD | wx.TE_PROCESS_ENTER
        self.password = wx.TextCtrl(self, -1, '', style=passwd_style)
        self.ok_button = wx.Button(self, -1, 'OK')
        self.ok_button.Bind(wx.EVT_BUTTON, self.OnOk)
        self.password.Bind(wx.EVT_TEXT_ENTER, self.OnOk)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.notice, 0, wx.ALL, 5)
        sizer.Add(self.password, 1, wx.ALL | wx.EXPAND, 5)
        sizer.Add(self.ok_button, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.SetFocus()

    def OnOk(self, event):
        """
        Called on OK button press.

        """
        if event:
            event.Skip(False)
        result = 1
        try:
            password_checker = controller.project.check_password
            if password_checker(self.project_id, self.password.GetValue()):
                result = 0
        except Exception as excp:
            LOGGER.exception('OnOk Exception: {0!s}'.format(excp))
            self.EndModal(1)
        self.EndModal(result)


class ProjectSelectDialog(wx.Dialog):
    """
    A dialog for selecting a project.

    :param parent: Parent frame.
    :type parent: :py:class:`wx.Frame`

    """
    def __init__(self, parent):
        wx.Dialog.__init__(self,
                           parent=parent,
                           id=wx.ID_ANY,
                           title='Project Selection',
                           size=(400, 300),
                           style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
        self.parent = parent
        self.diwa_state = parent.diwa_state
        self.project_index = []
        self.project_list = wx.ListBox(self, wx.ID_ANY, choices=[],
                                       style=wx.LB_SINGLE)

        self.project_list.Bind(wx.EVT_LISTBOX_DCLICK, self.OnProjectSelect)
        self.project_list.Bind(wx.EVT_LISTBOX, self.OnSelectionChange)
        self.UpdateProjects()

        if self.diwa_state.current_project:
            project_id = self.diwa_state.current_project_id
            list_index = self.project_index.index(project_id)
            self.project_list.SetSelection(list_index)

        self.add_button = wx.Button(self, wx.ID_ANY, 'Create...')
        self.edit_button = wx.Button(self, wx.ID_ANY, 'Modify...')
        self.delete_button = wx.Button(self, wx.ID_ANY, 'Delete...')
        self.select_button = wx.Button(self, wx.ID_ANY, 'Select')
        self.cancel_button = wx.Button(self, wx.ID_ANY, 'Cancel')

        self.add_button.Bind(wx.EVT_BUTTON, self.OnProjectAdd)
        self.edit_button.Bind(wx.EVT_BUTTON, self.OnProjectEdit)
        self.edit_button.Disable()
        self.delete_button.Bind(wx.EVT_BUTTON, self.OnProjectDelete)
        self.delete_button.Disable()
        self.select_button.Bind(wx.EVT_BUTTON, self.OnProjectSelect)
        self.select_button.Disable()
        self.cancel_button.Bind(wx.EVT_BUTTON, self.OnCancel)

        # Layout
        main_sizer_h = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer_v = wx.BoxSizer(wx.VERTICAL)
        button_sizer = wx.BoxSizer(wx.VERTICAL)
        selection_sizer = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer_h.Add(self.project_list, 1, wx.EXPAND, 0)
        button_sizer.Add(self.add_button)
        button_sizer.Add(self.edit_button)
        button_sizer.Add(self.delete_button)
        selection_sizer.Add(self.select_button)
        selection_sizer.Add(self.cancel_button)
        main_sizer_h.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 5)
        main_sizer_v.Add(main_sizer_h, 1, wx.EXPAND)
        main_sizer_v.Add(selection_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 5)
        self.SetSizer(main_sizer_v)
        self.Layout()

        if self.diwa_state.current_project:
            self.select_button.Enable()
            self.edit_button.Enable()
            self.delete_button.Enable()
        self.Refresh()

    def OnSelectionChange(self, event):
        """
        Event handler for selection change of the listbox.

        """
        if self.project_list.GetSelection() != wx.NOT_FOUND:
            self.select_button.Enable()
            self.edit_button.Enable()
            self.delete_button.Enable()
        else:
            self.select_button.Disable()
            self.edit_button.Disable()
            self.delete_button.Disable()
        if event:
            event.Skip()

    def OnCancel(self, event):
        """
        Handles "Cancel" button presses.

        :param event: GUI Event.
        :type event: Event

        """
        event.Skip(False)
        self.EndModal(0)

    def OnProjectAdd(self, event):
        """
        Shows a modal dialog for adding a new project.

        :param event: GUI Event.
        :type event: Event

        """
        project_id = 0
        try:
            params = {'title': 'Create a Project'}
            project_id = show_modal_and_destroy(AddProjectDialog, self.parent,
                                                params)
            if project_id < 0:
                self.EndModal(0)
            if project_id == 0:
                return
            self.UpdateProjects()
            LOGGER.debug('Added project: {0}'.format(project_id))
            if project_id not in self.project_index:
                msg = ('The project was not updated to database for some '
                       'reason!')
                LOGGER.exception(msg)
                show_modal_and_destroy(ErrorDialog, self, {'message': msg})
                event.Skip()
                self.EndModal(0)
            index = self.project_index.index(project_id)
            if index >= 0:
                self.project_list.SetSelection(index)
            self.OnSelectionChange(None)
        except (ValueError, IOError, OSError):
            LOGGER.exception('Add event exception')
        self.EndModal(project_id)

    #----------------------------------------------------------------------
    def OnProjectEdit(self, event):
        """
        Shows a modal dialog for adding a new project.

        :param event: GUI Event.
        :type event: Event

        """
        try:
            select_index = self.project_list.GetSelection()
            project_id = self.project_index[select_index]
            params = {
                'title': 'Modify a Project',
                'project_id': project_id
            }
            show_modal_and_destroy(AddProjectDialog, self, params)
            self.UpdateProjects()
            if project_id > 0:
                if project_id in self.project_index:
                    select_index = self.project_index.index(project_id)
                self.project_list.SetSelection(select_index)
        except Exception as excp:
            LOGGER.exception('Edit event exception: {0!s}'.format(excp))
        if event:
            event.Skip()

    def OnProjectDelete(self, event):
        """
        Handles the selection of a project.
        Starts a :class:`wos.CURRENT_PROJECT`, if necessary.
        Shows a dialog of the selected project.

        :param evt: GUI Event.
        :type evt: Event

        """
        selection = self.project_list.GetSelection()
        if selection == wx.NOT_FOUND:
            msg = 'The project does not seem to exist anymore.'
            show_modal_and_destroy(ErrorDialog, self, {'message': msg})
            return
        project_id = self.project_index[selection]
        if project_id == self.diwa_state.current_project_id:
            msg = 'You cannot delete currently active project.'
            show_modal_and_destroy(ErrorDialog, self, {'message': msg})
            return
        params = {
            'title': 'Delete Project',
            'project_id': project_id
        }
        result = show_modal_and_destroy(DeleteProjectDialog, self, params)
        if not result:
            return
        result_object = {
            'delete': (result & 1) > 0,
            'files': (result & 2) > 0
        }
        LOGGER.debug('OnProjectDelete result: {0}'.format(result_object))
        if result_object['delete']:
            if result_object['files']:
                project = Project.get_by_id(project_id)
                filesystem.delete_directory(project.dir)
                project = None
            controller.delete_record(Project, project_id)
            self.UpdateProjects()
        if event:
            event.Skip()

    def OnProjectSelect(self, event):
        """
        Handles the selection of a project.

        Starts a :class:`wos.CURRENT_PROJECT`, if necessary.
        Shows a dialog of the selected project.

        :param event: GUI Event.
        :type event: Event

        """
        selected = self.project_list.GetSelection()
        if selected == wx.NOT_FOUND:
            if event:
                event.Skip()
            return
        project_id = self.project_index[selected]
        project = Project.get_by_id(project_id)
        if not project:
            msg = 'The project does not seem to exist anymore!'
            show_modal_and_destroy(ErrorDialog, self, {'message': msg})
            self.Show()
            if event:
                event.Skip()
            return
        if project.password:
            screens = controller.common.NODE_SCREENS
            if screens < 1:
                self.Hide()
                msg = ('Can not select password protected project if screens '
                       'configuration is set to hidden (off)')
                show_modal_and_destroy(ErrorDialog, self, {'message': msg})
                self.Show()
                if event:
                    event.Skip()
                return
            params = {
                'title': 'Project Authentication',
                'project_id': project_id
            }
            result = show_modal_and_destroy(ProjectAuthenticationDialog, self,
                                            params)
            if result != 0:
                msg = 'Project Authentication Failed'
                show_modal_and_destroy(ErrorDialog, self, {'message': msg})
                if event:
                    event.Skip()
                return
        LOGGER.debug('Project selected')
        if project_id != self.diwa_state.current_project_id:
            try:
                self.diwa_state.set_current_project(project_id)
            except Exception as excp:
                LOGGER.exception('index_parent_exception: {0!s}'.format(excp))
        try:
            params = {'project_id': project_id}
            result = show_modal_and_destroy(ProjectSelectedDialog, self,
                                            params)
            LOGGER.debug('Project selected result: {0!s}'.format(result))
            self.parent.OnProjectChanged()
            self.parent.diwa_state.on_session_changed(result == wx.ID_NO)
            if result == wx.ID_NO:
                self.parent.EnableSessionButton()
            self.parent.Refresh()
        except Exception as excp:
            LOGGER.exception('Project Selected Exception: {0!s}'.format(excp))
        LOGGER.debug('Asked to start session.')
        self.EndModal(0)

    def UpdateProjects(self, company_id=1):
        """
        Fetches all projects from the database, based on the company.

        :param company_id: A company id, the owner of the projects.
        :type company_id: Integer

        :returns: The total number of projects.
        :type: Integer

        """
        projects = controller.get_projects_by_company(company_id)
        self.project_list.Clear()
        self.project_index = []
        for project in projects:
            index = self.project_list.Append(project.name)
            self.project_index.insert(index, project.id)
        return len(projects)


class ProjectSelectedDialog(wx.Dialog):
    """
    A dialog for project selection confirmation.

    """
    ptext = (u'Project {name} has been selected. A new session will now '
             u'be started.')

    def __init__(self, parent, project_id):
        wx.Dialog.__init__(self, parent, title='Project Selected',
                           style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
                           size=(250, 200))
        try:
            project_name = Project.get_by_id(project_id).name
            ltext = ProjectSelectedDialog.ptext.format(name=project_name)
            self.notice = wx.StaticText(self, label=ltext)
            self.no_session = wx.CheckBox(self, -1,
                                         'No, do not start a new session.')
            self.ok_button = wx.Button(self, -1, 'OK')
            self.ok_button.Bind(wx.EVT_BUTTON, self.OnOk)
            self.sizer = wx.BoxSizer(wx.VERTICAL)
            self.sizer.Add(self.notice, 0, wx.ALL, 5)
            self.sizer.Add(self.no_session, 0, wx.ALL, 5)
            self.sizer.Add(self.ok_button, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
            self.SetSizer(self.sizer)
            self.sizer.Fit(self)
            self.SetFocus()
        except Exception as excp:
            LOGGER.exception('Dialog exception: {0!s}'.format(excp))
            self.EndModal(0)

    def OnOk(self, event):
        """
        Event handler for OK button press.

        :param event: GUI event.
        :type event: :py:class:`wx.Event`

        """
        event.Skip()
        self.EndModal(wx.ID_YES if self.no_session.GetValue() else wx.ID_NO)


class UpdateDialog(wx.Dialog):
    """
    A Dialog which notifies about a software update.
    Contains the URL which the user can click on.

    :param title: Title of the dialog.
    :type title: String

    :param url: URL of the update.
    :type url: String

    """
    ptext = ('An application update is available for {0} at'.\
             format(diwavars.APPLICATION_NAME))

    def __init__(self, title, url, *args, **kwargs):
        wx.Dialog.__init__(self, wx.GetApp().GetTopWindow(),
                           title='Version {0} is available'.format(title),
                           style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
                           *args, **kwargs)
        self.notice = wx.StaticText(self, label=UpdateDialog.ptext)
        LOGGER.debug('URL: {0} - {1}'.format(type(url).__name__, str(url)))
        self.link = wx.HyperlinkCtrl(self, label='here.', url=url)
        self.link.Bind(wx.EVT_HYPERLINK, self.UrlHandler)
        self.ok_button = wx.Button(self, -1, 'OK')
        self.ok_button.Bind(wx.EVT_BUTTON, self.OnOk)
        self.vsizer = wx.BoxSizer(wx.VERTICAL)
        self.hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.hsizer.Add(self.notice)
        self.hsizer.Add(self.link)
        self.vsizer.Add(self.hsizer)
        self.vsizer.Add(self.ok_button)
        self.SetSizer(self.vsizer)
        self.CenterOnScreen()
        self.vsizer.Fit(self)
        self.SetFocus()

    def OnOk(self, event):
        """
        Event handler for OK button press.

        :param event: GUI event.
        :type event: :py:class:`wx.Event`

        """
        event.Skip(False)
        self.EndModal(0)

    def UrlHandler(self, event):
        """
        Event handler for URL text press.

        :param event: GUI event.
        :type event: :py:class:`wx.Event`

        """
        event.Skip(False)
        webbrowser.open(self.link.GetURL())


class SendProgressBar(wx.ProgressDialog):
    """
    Implements file send progress bar...

    """
    def __init__(self, parent, title, ypos):
        pd_style = (wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_AUTO_HIDE)
        wx.ProgressDialog.__init__(self, title=title, message='',
                                   parent=parent, style=pd_style)
        mypos = self.GetPositionTuple()
        self.MoveXY(mypos[0], mypos[1] + ypos)


class ChooseDiwaProfileDialog(wx.Dialog):
    """
    Allows user to select a DiWa profile from a list of profiles. Profiles
    are loaded from the filesystem.

    :param parent: The parent object.
    :type parent: Object

    :param profiles: List of profiles
    :type profiles: List

    """

    PROFILES_PATH = os.path.join(os.path.dirname(diwavars.CONFIG_PATH),
                                  'profiles')

    def __init__(self, parent, profiles):
        wx.Dialog.__init__(self,
                           parent=parent,
                           id=wx.ID_ANY,
                           title='Select DiWa Profile',
                           size=(400, 150),
                           style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
        self.parent = parent

        # Labels.
        dropdown_label = wx.StaticText(self, wx.ID_ANY, 'Select a profile:')

        # Configuration controls.
        style = wx.CB_DROPDOWN | wx.CB_READONLY | wx.CB_SORT
        self.dropdown = wx.ComboBox(self, wx.ID_ANY, choices=profiles,
                                    style=style)
        self.dropdown.Bind(wx.EVT_COMBOBOX, self.OnComboBox)

        # Other controls.
        self.ok_button = wx.Button(self, wx.ID_ANY, 'OK')
        self.ok_button.Bind(wx.EVT_BUTTON, self.SelectDiwaProfile)
        self.ok_button.Disable()
        exit_button = wx.Button(self, wx.ID_ANY, 'Exit')
        exit_button.Bind(wx.EVT_BUTTON, self.Exit)

        # Dialog sizers.
        dialog_sizer = wx.BoxSizer(wx.HORIZONTAL)
        dialog_sizer.Add(dropdown_label, 0, wx.ALL, 5)
        dialog_sizer.Add(self.dropdown, 1, wx.EXPAND | wx.ALL, 5)

        # Layout.
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer.Add(dialog_sizer, 0, wx.EXPAND | wx.ALL, 5)
        button_sizer.Add(self.ok_button, 0, wx.ALL, 5)
        button_sizer.Add(exit_button, 0, wx.ALL, 5)
        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.TOP, 10)
        self.SetSizer(main_sizer)
        self.Center()
        self.SetFocus()

    def OnComboBox(self, event):
        """
        Event handler for updating the state of OK button, depending
        if there's anything selected in the combo-box.

        :param event: GUI event.
        :type event: :py:class:`wx.Event`

        """
        if self.dropdown.GetSelection() == -1:
            self.ok_button.Disable()
        else:
            self.ok_button.Enable()

    @staticmethod
    def ListDatabaseProfiles():
        """
        Returns the list of available profiles.

        :returns: A list of profiles.
        :rtype: List of Strings

        """
        profiles = []

        for rdf in os.walk(ChooseDiwaProfileDialog.PROFILES_PATH):
            files = rdf[2]
            for file_ in files:
                profiles.append(os.path.splitext(file_)[0])
        return profiles

    def SelectDiwaProfile(self, event):
        """
        Load settings from a profile, event handler.

        :param event: GUI event.
        :type event: :py:class:`wx.Event`

        """
        selected = self.dropdown.GetValue()
        LOGGER.info('Selected database profile: {0}'.format(selected))
        valid_profile = 0
        path = '{0}.ini'.format(selected)
        path = os.path.join(ChooseDiwaProfileDialog.PROFILES_PATH, path)
        config_ = ConfigObj(path)
        wanted = ('DB_ADDRESS', 'DB_NAME', 'DB_TYPE', 'DB_USER', 'DB_PASS')
        if all((k in config_) for k in wanted):
            values = [config_[k] for k in wanted]
            diwavars.update_database_vars(*values)
            modelsbase.update_database()
            valid_profile += 1
        if 'PGM_GROUP' in config_:
            diwavars.update_pgm_group(config_['PGM_GROUP'])
            valid_profile += 1
        if 'STORAGE' in config_:
            diwavars.update_storage(config_['STORAGE'])
            valid_profile += 1
        wanted = ('CAMERA_URL', 'CAMERA_USER', 'CAMERA_PASS')
        if all((k in config_) for k in wanted):
            values = [config_[k] for k in wanted]
            diwavars.update_camera_vars(*values)
        if valid_profile != 3:
            msg = ('The profile you selected is invalid . Please select '
                   'another profile.')
            params = {'message': msg, 'caption': 'Invalid profile',
                      'style': wx.OK | wx.ICON_ERROR}
            show_modal_and_destroy(wx.MessageDialog, self, params)
            return
        diwavars.set_using_diwa_profile(True)
        self.EndModal(0)

    def Exit(self, event):
        """
        Event handler for Exit button press.

        :param event: GUI event.
        :type event: :py:class:`wx.Event`

        """
        self.EndModal(1)
