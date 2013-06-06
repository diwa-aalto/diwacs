'''
Created on 4.6.2013

:author: neriksso

'''
# System imports
import logging
import webbrowser

# Third party imports
from sqlalchemy import exc
import wx

# Own imports
import controller
import diwavars
from models import Company, Project
import filesystem
import utils


logging.config.fileConfig('logging.conf')
logger = logging.getLogger('dialogs')
CONTROLLED = False
CONTROLLING = False


class AddProjectDialog(wx.Dialog):
    """
    A dialog for adding a new project

    :param parent: Parent frame.
    :type parent: :class:`wx.Frame`

    :param title: A title for the dialog.
    :type title: String

     """
    def __init__(self, parent, title, project_id=None):
        super(AddProjectDialog, self).__init__(parent=parent,
            title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
            size=(250, 200))
        self.add_label = 'Create'
        dir_label_text = 'Project Folder Name (optional):'
        password_label_text = 'Project Password (optional):'
        self.project_id = 0
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
        password_label = wx.StaticText(self, label=password_label_text)
        self.password = wx.TextCtrl(self, wx.ID_ANY, style=wx.TE_PASSWORD)
        vbox.Add(password_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        vbox.Add(self.password, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
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
        self.dir.Bind(wx.EVT_TEXT, self.OnText)
        self.password.Bind(wx.EVT_TEXT, self.OnText)
        vbox.Fit(self)

    def OnAdd(self, e):
        """
        Handles the addition of a project to database, when "Add" button
        is pressed.

        :param e: GUI Event.
        :type e: Event

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
            logger.debug(self.project_id)
            self.Endmodal(self.project_id)
        else:
            db = controller.ConnectToDatabase()
            company = db.query(Company).filter(Company.id == 1).one()
            company_name = company.name
            data = {'project': {'name': self.name.GetValue(),
                                'dir': self.dir.GetValue(),
                                'password': self.password.GetValue()},
                    'company': {'name': company_name}
                    }
            project = controller.AddProject(data)
            logger.debug(project)
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

    def OnText(self, e):
        oSource = e.GetEventObject()
        sSource = oSource.GetValue()
        logger.debug('oSource: "%s" len(%s)' % (sSource, str(len(sSource))))
        if oSource == self.dir:
            self.password.SetEditable(len(sSource) == 0)
            e.Skip(len(self.password.GetValue()) > 0)
        else:
            self.dir.SetEditable(len(sSource) == 0)
            e.Skip(len(self.dir.GetValue()) > 0)

    def OnClose(self, e):
        """
        Handles "Close" button presses.

        :param e: GUI Event.
        :type e: Event

        """
        e = e
        self.Destroy()


class CloseError(Exception):
    """
    Class describing an error while closing application.

    """
    def __init__(self, *args, **kwds):
        Exception.__init__(self, *args, **kwds)

    def __str__(self):
        return 'CloseError'


class ConnectionErrorDialog(wx.ProgressDialog):
    """
    Create a connection error dialog that informs the user about reconnection
    attempts made by the software.

    """
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
            keepGoing = not (filesystem.TestStorageConnection() and
                             controller.TestConnection())
            if count % 4 == 0:
                self.Update(count, "Reconnecting.. DiWaCS will shutdown in %d"\
                            " seconds, if no connection is made. " %
                            ((imax - count) / 4))
        self.result = keepGoing


class CreateProjectDialog(wx.Dialog):
    """
    A dialog for project creation.

    """
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
        if self.project_id:
            controller.EditProject(self.project_id,
                {'name': self.name.GetValue(),
                 'dir': self.dir.GetValue()
                }
            )
            self.Destroy()
        else:
            try:
                db = controller.ConnectToDatabase()
                company = db.query(Company).filter(Company.id == 1).one()
                company_name = company.name
                data = {'project': {'name': self.name.GetValue(),
                                    'dir': self.dir.GetValue(),
                                    'password': self.password.GetValue()},
                        'company': {'name': company_name}
                        }
                self.project = controller.AddProject(data)
                self.Destroy()
            except:
                logger.exception("create project exception")

    def OnCancel(self, unused_event):
        self.Destroy()


class DeleteProjectDialog(wx.Dialog):
    """
    A dialog for deleting project.

    """
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
            logger.exception("Dialog exception")
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


class PreferencesDialog(wx.Dialog):
    """
    Creates and displays a preferences dialog that allows the user to
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
        openBtn.Bind(wx.EVT_BUTTON, self.OpenConfig)
        saveBtn = wx.Button(self, wx.ID_ANY, "OK")
        saveBtn.Bind(wx.EVT_BUTTON, self.SavePreferences)
        cancelBtn = wx.Button(self, wx.ID_ANY, "Cancel")
        cancelBtn.Bind(wx.EVT_BUTTON, self.OnCancel)

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
        self.LoadPreferences()
        self.SetFocus()

    #----------------------------------------------------------------------
    def LoadPreferences(self):
        """
        Load the current preferences and fills the text controls.

        """
        screens = self.config['SCREENS']
        name = self.config['NAME']
        logger.debug("config:%s" % str(self.config))
        if int(screens) == 0:
            self.screens_hidden.SetValue(1)
        else:
            self.screens_show.SetValue(1)
        self.name_value.SetValue(name)

    #----------------------------------------------------------------------
    def OpenConfig(self, unused_event):
        """
        Opens config file.

        :param event: GUI event.
        :type event: Event

        """
        filesystem.OpenFile(diwavars.CONFIG_PATH)

    #----------------------------------------------------------------------
    def OnCancel(self, unused_event):
        """Closes the dialog without modifications.

        :param event: GUI event.
        :type event: Event

        """
        self.EndModal(0)

    #----------------------------------------------------------------------
    def SavePreferences(self, event):
        """Save the preferences.

        :param event: GUI Event.
        :type event: Event

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


class ProjectAuthenticationDialog(wx.Dialog):
    """
    A dialog for project authentication.

    """
    def __init__(self, parent, title, project_id):
        super(ProjectAuthenticationDialog, self).__init__(parent=parent,
            title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
            size=(250, 200))
        try:
            self.parent = parent
            self.project = controller.GetProject(project_id)
            labeltext = ('Please enter password for Project %s' %
                         self.project.name)
            self.notice = wx.StaticText(self, label=labeltext)
            self.password = wx.TextCtrl(self, -1, '',
                                        style=wx.TE_PASSWORD |
                                        wx.TE_PROCESS_ENTER)
            self.ok = wx.Button(self, -1, "OK")
            self.ok.Bind(wx.EVT_BUTTON, self.OnOk)
            self.password.Bind(wx.EVT_TEXT_ENTER, self.OnOk)
            self.sizer = wx.BoxSizer(wx.VERTICAL)
            self.sizer.Add(self.notice, 0, wx.ALL, 5)
            self.sizer.Add(self.password, 1, wx.ALL | wx.EXPAND, 5)
            self.sizer.Add(self.ok, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
            self.SetSizer(self.sizer)
            self.sizer.Fit(self)
            self.SetFocus()
        except:
            logger.exception("Dialog exception")
            self.EndModal(1)

    def OnOk(self, unused_event):
        self.EndModal(0 if utils.CheckProjectPassword(self.project.id,
                                            self.password.GetValue()) else 1)


class ProjectSelectDialog(wx.Dialog):
    """
    A dialog for selecting a project.

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
        cancelBtn.Bind(wx.EVT_BUTTON, self.OnCancel)
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

    def OnCancel(self, unused_event):
        """
        Handles "Cancel" button presses.

        :param event: GUI Event.
        :type event: Event

        """
        self.EndModal(0)

    #----------------------------------------------------------------------
    def EditEvent(self, unused_event):
        """
        Shows a modal dialog for adding a new project.

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
            logger.exception("Edit event exception")

    def AddEvent(self, unused_event):
        """
        Shows a modal dialog for adding a new project.

        :param event: GUI Event.
        :type event: Event

        """
        try:
            dlg = AddProjectDialog(self, 'Create a Project')
            project_id = dlg.ShowModal()
            self.projects = self.GetProjects()
            self.project_list.Set(self.projects)
            logger.debug(project_id)
            if project_id:
                self.project_list.SetSelection(int(
                                self.project_index.index(project_id)))
                self.OnLb(None)

        except:
            logger.exception("Add event exception")

    def DelEvent(self, unused_event):
        """
        Handles the selection of a project.
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
            logger.debug(result)
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
        """
        Handles the selection of a project.

        Starts a :class:`wos.CURRENT_PROJECT`, if necessary.
        Shows a dialog of the selected project.

        :param evt: GUI Event.
        :type evt: Event

        """
        index = self.project_index[self.project_list.GetSelection()]
        if controller.GetProject(index).password:
            myModal = ProjectAuthenticationDialog(self.parent,
                                                  'Project Authentication',
                                                  index)
            auth = myModal.ShowModal()
            if not auth == 0:
                dlg = wx.MessageDialog(self, "Project Authentication Failed",
                                       style=wx.OK | wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
                return
        logger.debug('Project selected')
        if index != self.parent.current_project_id:
            self.parent.SetCurrentProject(index)
            self.parent.OnProjectSelected()

        dlg = ProjectSelectedDialog(self, 'Project Selected', index)
        try:
            result = dlg.ShowModal()
            logger.debug(result)
            if result == 1:
                self.parent.OnSession(None)
            elif result == 2:
                self.parent.current_session_id = -1
                # No session should be started here.
                self.parent.OnSession(None)
        finally:
            dlg.Destroy()
        logger.debug('Asked to start session.')
        self.EndModal(0)

    def GetProjects(self, company_id=1):
        """
        Fetches all projects from the database, based on the company.

        :param company_id: A company id, the owner of the projects.
        :type company_id: Integer

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
            logger.exception("Project Select Dialog exception")


class ProjectSelectedDialog(wx.Dialog):
    """
    A dialog for project selection confirmation.

    """
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
            logger.exception("Dialog exception")
            self.EndModal(0)

    def OnOk(self, unused_event):
        self.EndModal(2 if self.cb.GetValue() else 1)


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
