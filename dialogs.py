"""
Created on 4.6.2013

:platform: Windows Vista, Windows 7, Windows 8
:synopsis: Define the pop-up dialogs for the application.
:note: Requires WxPython.
:author: neriksso

"""
# System imports
from logging import config, getLogger
import webbrowser

# Third party imports
import wx

# Own imports
import controller
import diwavars
from models import Company, Project
import filesystem
import utils


LOGGER = None

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
        LOGGER.exception('Exception in %s: %s', str(class_), str(excp))
    finally:
        try:
            if hasattr(dialog, 'Destroy'):
                dialog.Destroy()
        except Exception:
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

        LOGGER.debug('AddProjectDebug:\n'
                     'AddProjectDialog(self, parent=%(parent)s, '
                     'title=%(title)s, style=%(style)d, size=%(size)s)',
                     locals())

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
            project = controller.add_project(data)
            LOGGER.info('Created Project: %s (id=%d)',
                        project.name,
                        project.id)
            result = project.id
        except Exception as excp:
            LOGGER.exception('Error in add project: %s', str(excp))
            self.EndModal(0)
            return

        if not result:
            LOGGER.exception('ERROR in add project!')
            self.EndModal(0)
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
                if dlg_result == wx.ID_YES:
                    self.parent.OnSession(None)
        except Exception as excp:
            log_msg = 'Exception in Project creation: {0!s}'
            LOGGER.exception(log_msg.format(excp))
        self.EndModal(result)

    def OnText(self, event):
        """
        Event handler for text changed.

        """
        source_object = event.GetEventObject()
        source_string = source_object.GetValue()
        if source_object == self.dir:
            self.password.SetEditable(len(source_string) == 0)
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
        return 'CloseError'

    def __unicode__(self):
        return u'CloseError'


class ConnectionErrorDialog(wx.ProgressDialog):
    """
    Create a connection error dialog that informs the user about reconnection
    attempts made by the software.

    """
    stat_text = ('Reconnecting... DiWaCS will shutdown in %s seconds if ' +
                 'no connection is made.')
    imax = 80

    def __init__(self, parent):
        self.parent = parent
        wx.ProgressDialog.__init__(self, 'Connection Error',
                                   ConnectionErrorDialog.stat_text % str(20),
                                   maximum=ConnectionErrorDialog.imax,
                                   parent=self.parent,
                                   style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)

    def GetResult(self):
        keep_going = True
        count = 0
        while keep_going and count < ConnectionErrorDialog.imax:
            count += 1
            wx.MilliSleep(250)
            keep_going = not (filesystem.test_storage_connection() and
                             controller.test_connection())
            if count % 4 == 0:
                seconds = str((ConnectionErrorDialog.imax - count) / 4)
                self.Update(count, ConnectionErrorDialog.stat_text % seconds)
        return keep_going


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

        label_text = ('You are about to delete project %s permanently.'
                      ' Are you really sure?') % self.project.name
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

        # Labels.
        screens_label = wx.StaticText(self, wx.ID_ANY, 'Screen visibility:')
        commands_label = wx.StaticText(self, wx.ID_ANY, 'Run commands:')
        name_label = wx.StaticText(self, wx.ID_ANY, 'Name:')

        # Configuration controls.
        self.screens_hidden = wx.RadioButton(self, wx.ID_ANY,
                                             'Off (recommended)',
                                             style=wx.RB_GROUP)
        self.screens_show = wx.RadioButton(self, wx.ID_ANY,
                                           'On (not recommended)')
        self.commands_on = wx.RadioButton(self, wx.ID_ANY, 'On (recommended)',
                                          style=wx.RB_GROUP)
        self.commands_off = wx.RadioButton(self, wx.ID_ANY,
                                           'Off (not recommended')
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
        self.screens_hidden.SetToolTip(wx.ToolTip(txt_screens_off))
        self.screens_show.SetToolTip(wx.ToolTip(txt_screens_on))
        self.commands_off.SetToolTip(wx.ToolTip(txt_commands_off))
        self.commands_on.SetToolTip(wx.ToolTip(txt_commands_on))

        # Other controls.
        open_button = wx.Button(self, wx.ID_ANY, 'Config File')
        open_button.Bind(wx.EVT_BUTTON, self.OpenConfig)
        save_button = wx.Button(self, wx.ID_ANY, 'OK')
        save_button.Bind(wx.EVT_BUTTON, self.SavePreferences)
        cancel_button = wx.Button(self, wx.ID_ANY, 'Cancel')
        cancel_button.Bind(wx.EVT_BUTTON, self.OnCancel)

        # Preferences sizers.
        preferences_sizer = wx.FlexGridSizer(cols=2, hgap=8, vgap=8)
        preferences_sizer.AddGrowableCol(1)
        radio_sizer_screens = wx.BoxSizer(wx.HORIZONTAL)
        radio_sizer_commands = wx.BoxSizer(wx.HORIZONTAL)

        radio_sizer_screens.Add(self.screens_hidden)
        radio_sizer_screens.AddSpacer(5)
        radio_sizer_screens.Add(self.screens_show)
        radio_sizer_commands.Add(self.commands_off)
        radio_sizer_commands.AddSpacer(5)
        radio_sizer_commands.Add(self.commands_on)

        # Layout Preferences.
        preferences_sizer.Add(screens_label, 0,
                              wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        preferences_sizer.Add(radio_sizer_screens, 0, wx.EXPAND)

        preferences_sizer.Add(commands_label, 0,
                              wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        preferences_sizer.Add(radio_sizer_commands, 0, wx.EXPAND)

        preferences_sizer.Add(name_label, 0,
                              wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        preferences_sizer.Add(self.name_value, 0, wx.EXPAND)

        # Layout.
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer.Add(preferences_sizer, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(open_button, 0, wx.ALIGN_RIGHT | wx.RIGHT, 5)
        button_sizer.Add(save_button, 0, wx.ALL, 5)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)
        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.TOP, 30)
        self.SetSizerAndFit(main_sizer)

        # load preferences
        self.LoadPreferences()
        self.SetFocus()

    #----------------------------------------------------------------------
    def LoadPreferences(self):
        """
        Load the current preferences and fills the text controls.

        """
        screens = self.config['SCREENS']
        commands = self.config['RUN_CMD']
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
        self.config['NAME'] = self.name_value.GetValue()
        controller.set_node_name(self.config['NAME'])
        self.config.write()
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
        labeltext = ('Please enter password for Project %s' %
                     self.project.name)
        self.notice = wx.StaticText(self, label=labeltext)
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
            LOGGER.exception('OnOk EXception: %s', str(excp))
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
            if not project_id or project_id < 1:
                return
            self.UpdateProjects()
            LOGGER.debug('Added project: %d', project_id)
            if project_id not in self.project_index:
                msg = ('The project was not updated to database for some '
                       'reason!')
                LOGGER.exception(msg)
                show_modal_and_destroy(ErrorDialog, self, {'message': msg})
                event.Skip()
                return
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
            params = {'title': 'Modify a Project',
                      'project_id': project_id}
            show_modal_and_destroy(AddProjectDialog, self, params)
            self.UpdateProjects()
            if project_id:
                if project_id in self.project_index:
                    select_index = self.project_index.index(project_id)
                self.project_list.SetSelection(select_index)
        except:
            LOGGER.exception('Edit event exception')
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
        params = {'title': 'Delete Project',
                  'project_id': project_id}
        result = show_modal_and_destroy(DeleteProjectDialog, self, params)
        result_object = {'delete': (result & 1) > 0,
                         'files': (result & 2) > 0}
        LOGGER.debug('OnProjectDelete result: ' + str(result_object))
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
                msg = ('Can not select password protected project if screens'
                       ' configuration is set to hidden (off)')
                show_modal_and_destroy(ErrorDialog, self, {'message': msg})
                self.Show()
                if event:
                    event.Skip()
                return
            params = {'title': 'Project Authentication',
                      'project_id': project_id}
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
                LOGGER.exception('index_parent_exception: %s', str(excp))
        try:
            params = {'project_id': project_id}
            result = show_modal_and_destroy(ProjectSelectedDialog, self,
                                            params)
            LOGGER.debug('Project selected result: %s', str(result))
            self.parent.OnProjectChanged()
            self.parent.diwa_state.on_session_changed(result == 1)
            if result == 1:
                self.parent.EnableSessionButton()
            self.parent.Refresh()
        except Exception as excp:
            LOGGER.exception('Project Selected Exception: %s', str(excp))
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
            self.cancel_button = wx.CheckBox(self, -1,
                                         'No, do not start a new session.')
            self.ok_button = wx.Button(self, -1, 'OK')
            self.ok_button.Bind(wx.EVT_BUTTON, self.OnOk)
            self.sizer = wx.BoxSizer(wx.VERTICAL)
            self.sizer.Add(self.notice, 0, wx.ALL, 5)
            self.sizer.Add(self.cancel_button, 0, wx.ALL, 5)
            self.sizer.Add(self.ok_button, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
            self.SetSizer(self.sizer)
            self.sizer.Fit(self)
            self.SetFocus()
        except Exception as excp:
            LOGGER.exception('Dialog exception: %s', str(excp))
            self.EndModal(0)

    def OnOk(self, event):
        event.Skip()
        self.EndModal(2 if self.cancel_button.GetValue() else 1)


class UpdateDialog(wx.Dialog):
    """
    A Dialog which notifies about a software update.
    Contains the URL which the user can click on.

    :param title: Title of the dialog.
    :type title: String

    :param url: URL of the update.
    :type url: String

    """
    ptext = ('An application update is available for %s at' %
             diwavars.APPLICATION_NAME)

    def __init__(self, title, url, *args, **kwargs):
        wx.Dialog.__init__(self, wx.GetApp().GetTopWindow(),
                           title='Version %s is available' % title,
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
        event.Skip(False)
        self.EndModal(0)

    def UrlHandler(self, event):
        event.Skip()
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
