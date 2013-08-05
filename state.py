"""
Created on 4.7.2013

:author: neriksso

"""
# Standard imports.
from ast import literal_eval
from base64 import b64decode
import cStringIO
from datetime import datetime, timedelta
from logging import config, getLogger
import os
from random import Random
import shutil
import webbrowser

# 3rd party imports.
import configobj
from watchdog.observers import Observer
import wx

# Own imports.
import controller
from dialogs import show_modal_and_destroy
import diwavars
import filesystem
import graphicaldesign
import macro
from modelsbase import REVERSE_ACTIONS
from models import Project, Session
import swnp
import threads
import utils


LOGGER = None


def __init_logger():
    """
    Used to initialize the logger, when running from diwa client
    (not intended for use when imported for unit tests).

    """
    global LOGGER
    config.fileConfig('logging.conf')
    LOGGER = getLogger('state')


def __set_logger_level(level):
    """
    Sets the logger level for state logger.

    :param level: Level of logging.
    :type level: Integer

    """
    LOGGER.setLevel(level)


diwavars.add_logger_initializer(__init_logger)
diwavars.add_logger_level_setter(__set_logger_level)


class SessionChangeException(Exception):
    pass


def initialization_test():
    """
    Used to test that we have are good to go.

    At this time only includes test_connection() from controller, but
    more tests could be added here.

    """
    error = ''
    if not error and not controller.test_connection():
        error += 'Database connection failed.\n'
    if error:
        error += 'Press OK to exit.'
        LOGGER.error(error)
        return error
    return False


def create_config():
    """
    Creates a config file.

    This actually just copies the default one from installation folder
    to the ~wos settings folder.

    """
    try:
        os.makedirs(os.path.dirname(diwavars.CONFIG_PATH))
    except OSError:
        pass
    shutil.copy('config.ini', diwavars.CONFIG_PATH)


def load_config():
    """
    Loads a config file, creating it if it does not exists.

    """
    if not os.path.exists(diwavars.CONFIG_PATH):
        create_config()
    return configobj.ConfigObj(diwavars.CONFIG_PATH)


class State(object):
    """
    Used to represent the state of the client.

    All the graphical buttons etc have been removed from here and
    they are part of the main GraphicalUserInterface class right now.
    Likewise that class should minimize making direct changes to the
    current status of the software and only interpret user input.

    """
    DEF_SIZE = 2 * 1024 * 1024
    DEF_FILES = 40
    DEF_BUFFER = 1024 * 1024

    def __init__(self, parent):
        diwavars.update_windows_version()
        self.parent = parent
        try:
            self.audio_recorder = threads.AudioRecorder(self)
            self.audio_recorder.daemon = True
        except Exception as excp:
            LOGGER.exception('Audio recorder exception: %s', str(excp))
        self.exited = False
        self.responsive = ''
        self.is_responsive = False
        self.screen_selected = None
        self.error_th = threads.CONNECTION_ERROR_THREAD(self.parent)
        self.random = Random()
        self.error_th.daemon = True
        self.error_th.start()
        self.worker = threads.WORKER_THREAD(parent)
        self.swnp = None
        self.config_was_created = False
        try:
            # Parse the config.
            self.config_was_created = not os.path.exists(diwavars.CONFIG_PATH)
            diwavars.set_config(load_config())
            self.worker.parse_config(diwavars.CONFIG)
            screens = int(diwavars.CONFIG['SCREENS'])
            name = diwavars.CONFIG['NAME']
            #:FIXME: What the actual?
            node_id = 'observer' if self.is_responsive else ''
            self.swnp = swnp.SWNP(
                pgm_group=int(diwavars.PGM_GROUP),
                screens=screens,
                name=name,
                node_id=node_id,
                error_handler=self.error_th
            )
        except Exception as excp:
            LOGGER.exception('loading config exception: %s', str(excp))
        self.initialized = False
        self.cmfh = None
        self.capture_thread = None
        # Project
        self.current_project = None
        self.current_project_id = 0
        self.current_project_thread = threads.CURRENT_PROJECT(self.swnp)
        self.current_project_thread.daemon = True
        # Session
        self.current_session = None
        self.current_session_id = 0
        self.current_session_thread = threads.CURRENT_PROJECT(self.swnp)
        self.current_session_thread.deamon = True
        # Other
        self.activity = None
        self.project_observer = None
        self.scan_observer = None
        activity = controller.get_active_activity(diwavars.PGM_GROUP)
        self.selected_nodes = activity.id if activity else 0
        self.current_project_id = 0
        self.current_session_id = 0
        self.controlled = None
        self.controlling = None

    def initialize(self):
        """
        Finish the initialization (2-stage init).

        :note:
            As this is not so essential, we could just stick it up to
            the __init__ but there might be something that needs to be
            done in between the __init__ and these calls here.

        """
        try:
            self.worker.remove_all_registry_entries()
            cmfh_initializer = threads.SEND_FILE_CONTEX_MENU_HANDLER
            self.cmfh = cmfh_initializer(self.parent,
                                         self.swnp.context,
                                         self.swnp_send,
                                         self.handle_file_send)
            self.cmfh.daemon = True
            self.cmfh.start()
            self.capture_thread = threads.INPUT_CAPTURE(self, self.swnp_send)
            self.capture_thread.daemon = True
            self.capture_thread.start()

            if self.activity and not self.is_responsive:
                pid = controller.get_project_id_by_activity(self.activity)
                sid = controller.get_session_id_by_activity(self.activity)
                self.set_current_project(pid)
                self.set_current_session(sid)
                self.parent.OnProject()
        except Exception as excp:
            LOGGER.exception('State.initialize exception: {0!s}'.format(excp))
            raise

    def destroy(self):
        """
        Part of the shutdown routine, closes all the threads under this.

        """
        if self.cmfh:
            LOGGER.debug('Cmfh closing...')
            self.cmfh.stop()
        if self.worker:
            LOGGER.debug('Registery closing...')
            self.worker.remove_all_registry_entries()
            LOGGER.debug('Worker closing...')
            self.worker.stop()
        if self.swnp:
            LOGGER.debug('Swnp closing...')
            self.swnp.close()
        if self.error_th:
            LOGGER.debug('Connection Error closing...')
            self.error_th.stop()
        LOGGER.debug('Closing extra threads')
        threads.DIWA_THREAD.stop_all()

    def _handle_file_copy(self, src_dst_list, dirs, dialog):
        """
        Mass copy files while giving optional output on the progress
        through a dialog.

        :param src_dst_list: A list of (Source, Target) filepaths.
        :type src_dst_list: A list of Tuples of Strings.

        :param dirs: All the directories to be created before copying.
        :type dirs: A list of strings.

        :param dialog: The progress dialog.
        :type dialog: :py:class:`wx.ProgressDialog`

        """
        total_len = 0
        total_copied = 0
        filecount = len(src_dst_list)
        for item in src_dst_list:
            total_len += os.path.getsize(item[0])
        do_updates = False
        if (dialog is not None and (total_len >= State.DEF_SIZE or
                                    filecount >= State.DEF_FILES)):
            LOGGER.debug('PROGRESS VISIBLE!')
            self.parent.Hide()
            dialog.Show()
            dialog.Raise()
            do_updates = True
        for directory in dirs:
            try:
                os.mkdir(directory)
            except IOError:
                pass
        first_transaction = True
        lastupdate = datetime.now()
        for i, (src, dst) in enumerate(src_dst_list):
            curlen = os.path.getsize(src)
            curcopied = 0
            fin = open(src, 'rb')
            fout = open(dst, 'wb')
            while curcopied < curlen:
                cstr = fin.read(min(State.DEF_BUFFER, curlen - curcopied))
                fout.write(cstr)
                curcopied += len(cstr)
                condition = do_updates and (
                    first_transaction or
                    (datetime.now() - lastupdate).total_seconds() > 1.0 or
                    curcopied == curlen
                )
                if condition:
                    lastupdate = datetime.now()
                    first_transaction = False
                    data = {
                        'filename': os.path.basename(src),
                        'filepercent': int(100.0 * curcopied / curlen),
                        'totalpercent': int(100.0 *
                                            (total_copied + curcopied) /
                                            total_len),
                        'file': i + 1,
                        'filecount': filecount
                    }
                    msg = ('{filename} {filepercent}%% complete (file {file} '
                           'out of {filecount}')
                    title = 'Sending items... {totalpercent}%% Complete'
                    title, msg = [s.format(**data) for s in (title, msg)]
                    dialog.SetTitle(title)
                    dialog.Update(data['totalpercent'], msg)
                # End of conditional.
            fin.close()
            fout.close()
            shutil.copystat(src, dst)
            total_copied += curlen
            self.parent.Update()
            first_transaction = True
        if do_updates:
            dialog.Update(100, 'file transfer complete')

    def handle_file_send(self, filenames, progressdialog=None):
        """
        Sends a file link to another node.

        First parses all the files and folder structure, then confirms weather
        the users wishes to add the items to project before beginning the copy
        routine.

        The copy routine first creates all the needed subfolders and then sums
        up all the file sizes to be copied. Then it will update the dialog
        in the beginning/end of every file transaction and whenever there's
        been more than 1 second from the last update dialog update. Assuming
        the progressdialog parameter has been given.

        The progress dialog, if supplied, is updated as follows:
            - If there's less than DEF_FILES (**40**) files the dialog \
            will not be shown or updated.
            - If the data size sum is less than DEF_SIZE (**2 MB**) the \
            dialog will not be shown or updated.
            - Title will contain the total percentage of data transfer.
            - Message will contain the percentage of current file transfer.
            - Progress bar is set to percent [0, 100] of the total data \
            transfer.

        :param filenames: All the files/folders to be copied.
        :type filenames: List of String

        :param progressdialog: The progress dialog to update (optional).
        :type progressdialog: :py:class:`wx.ProgressDialog`

        """
        path = self.current_project.path
        src_dst_list = []
        returnvalue = []
        contains_folders = False
        mydirs = []
        for filename in filenames:
            is_folder = os.path.isdir(filename)
            LOGGER.debug('File: %s', filename)
            if is_folder:
                contains_folders = True
                copyroot = filename
                cidx = len(copyroot) + 1
                res = os.path.join(path, os.path.basename(filename))
                LOGGER.debug('Project target: %s', res)
                mydirs.append(res)
                returnvalue.append(res)
                # os.mkdir(returnvalue)
                for (currentroot, dirs, files) in os.walk(copyroot, True):
                    relativeroot = ''
                    if len(currentroot) > cidx:
                        relativeroot = currentroot[cidx:]
                    targetroot = os.path.join(path, os.path.basename(filename),
                                              relativeroot)
                    LOGGER.debug('PTROOT: %s', targetroot)
                    for directory in dirs:
                        temp_path = os.path.join(targetroot, directory)
                        if not os.path.exists(temp_path):
                            mydirs.append(temp_path)
                            # os.makedirs(temp_path)
                            LOGGER.debug('CreatePath: %s', temp_path)
                    for fname in files:
                        t_source = os.path.join(currentroot, fname)
                        t_destination = os.path.join(targetroot, fname)
                        item = (t_source, t_destination)
                        src_dst_list.append(item)
            else:
                path_ = os.path.join(path, os.path.basename(filename))
                returnvalue.append(path_)
                src_dst_list.append((filename, path_))
        params = {'message': 'Add the dragged objects to project?',
                  'caption': 'Add to project?',
                  'style': (wx.ICON_QUESTION | wx.STAY_ON_TOP |
                            wx.YES_DEFAULT | wx.YES_NO)}
        result = show_modal_and_destroy(wx.MessageDialog, self.parent, params)
        if contains_folders and result == wx.ID_NO:
            params = {'message': ('When dragging folders, you need to add '
                                'them to project.'),
                      'caption': 'Denied action',
                      'style': (wx.ICON_WARNING | wx.OK | wx.OK_DEFAULT |
                                wx.STAY_ON_TOP)}
            show_modal_and_destroy(wx.MessageDialog, self.parent, params)
            return []
        if not contains_folders and result == wx.ID_NO:
            # Change project folders to temp folder.
            tmp = os.path.join(r'\\' + diwavars.STORAGE, 'Projects', 'temp')
            src_dst_list = [(src, dst.replace(path, tmp))
                             for src, dst in src_dst_list]
        try:
            self._handle_file_copy(src_dst_list, mydirs, progressdialog)
        except IOError as excp:
            LOGGER.exception('MYCOPY: %s', str(excp))
        return returnvalue

    def end_current_project(self):
        """
        End the current project.

        """
        if self.current_project_thread.isAlive():
            self.current_project_thread.stop()
        self.current_project_id = 0
        self.current_project = None

    def end_current_session(self):
        """
        End the current session.

        """
        log_msg = 'end_current_session({0})...'.format(self.current_session_id)
        LOGGER.debug(log_msg)
        controller.end_session(self.current_session_id)
        if self.current_session_thread.isAlive():
            self.current_session_thread.stop()
        self.current_session_id = 0
        self.current_session = None
        LOGGER.debug('end of end_current_session')

    def get_random_responsive(self):
        """
        Get a random node amongst all the responsive nodes.

        """
        nodes = self.swnp.get_list()
        #: TODO: Ask why this had the limitation?
        # nodes = [n for n in nodes if n.id <= 10]
        if len(nodes) < 2:
            self.set_responsive()
            return
        item = 255
        self.is_responsive = False
        self.swnp.set_responsive('')
        try:
            random_node = self.random.choice(nodes)
            item = random_node.id
        except IndexError:
            LOGGER.debug('get_random error: nodes empty')
            return
        LOGGER.debug('Random responsive is %d', item)
        self.swnp_send(item, 'set;responsive')

    TARGET_TO_FLAG = {0x201: 0x0002, 0x202: 0x0004, 0x204: 0x0008,
                      0x205: 0x0010, 0x207: 0x0020, 0x208: 0x0040,
                      0x20A: 0x0800, 0x20E: 0x1000}

    @staticmethod
    def _on_mouse_event(parameters):
        target, wheel = [int(i) for i in parameters.split(',')]
        flags = 0
        mouse_data = 0
        if target in State.TARGET_TO_FLAG:
            flags = State.TARGET_TO_FLAG[target]
        if target in [0x20A, 0x20E]:
            mouse_data = wheel * 120
        macro.send_input('m', (0, 0), flags, 0, mouse_data)

    @staticmethod
    def _on_mouse_move(parameters):
        pos_x, pos_y = [int(i) for i in parameters.split(',')]
        macro.send_input('m', (pos_x, pos_y), 0x0001)

    @staticmethod
    def _on_key(parameters):
        evt_code, key, scan = [int(i) for i in parameters.split(',')]
        flags = 0
        if evt_code == 257:
            flags = 2
        macro.send_input('k', key, flags, scan)

    @staticmethod
    def _on_url(parameters):
        LOGGER.debug('Open URL: {0}'.format(parameters))
        webbrowser.open(parameters)

    def _on_open(self, parameters):
        #  Open all files in list.
        target = literal_eval(parameters)
        for filename in target:
            log_msg = 'Opening file: {basename}'
            LOGGER.info(log_msg.format(basename=os.path.basename(filename)))
            if os.path.exists(filename):
                if self.current_session:
                    action_id = REVERSE_ACTIONS['Opened']
                    controller.create_file_action(filename, action_id,
                                                  self.current_session_id,
                                                  self.current_project_id)
                filesystem.open_file(filename)

    def _on_wx_image(self, parameters):
        image_data = b64decode(parameters)
        image_buffer = cStringIO.StringIO(image_data)
        wx_image = wx.EmptyImage()
        wx_image.LoadStream(image_buffer)
        if wx_image.Ok():
            graphicaldesign.ImageViewer(self.parent, wx_image)
        else:
            LOGGER.exception('Received invalid wx_image.')
        wx_image = None

    def _on_new_responsive(self, parameters):
        if self.is_responsive:
            self.stop_responsive()
            self.is_responsive = False
            self.responsive = parameters
            LOGGER.info('Responsive changed to: {0}'.format(parameters))

    def _on_event(self, parameters):
        LOGGER.info('event: {0}'.format(parameters))
        if self.is_responsive:
            self.worker.create_event(parameters)

    def _on_remote_start(self, parameters):
        macro.release_all_keys()
        self.controlled = parameters
        LOGGER.debug('CONTROLLED: {0}'.format(parameters))

    def _on_remote_end(self, parameters):  # @UnusedVariable
        if self.controlled:
            macro.release_all_keys()
        if self.controlling:
            self.parent.SetCursor(diwavars.DEFAULT_CURSOR)
            del self.selected_nodes[:]
            threads.inputcapture.set_capture(False)
            self.capture_thread.unhook()
            self.parent.overlay.Hide()
        self.controlled = False
        self.controlling = False

    def _on_set(self, parameters):
        if parameters == 'responsive':
            if diwavars.RESPONSIVE > 0:
                self.is_responsive = True
                self.set_responsive()

    def _on_screenshot(self, parameters):  # @UnusedVariable
        if self.swnp.node.screens > 0:
            LOGGER.info('Taking a screenshot.')
            project_path = self.current_project.path
            filesystem.screen_capture(project_path, self.swnp.node.id)

    def _on_current_activity(self, parameters):
        self.activity = int(parameters)
        old_project_id = self.current_project_id
        pid = controller.get_project_id_by_activity(self.activity)
        sid = controller.get_session_id_by_activity(self.activity)
        if old_project_id != pid:
            self.set_current_project(pid)
        self.set_current_session(sid)
        if old_project_id != pid:
            self.parent.OnProject()

    def _on_current_project(self, parameters):
        project_id = int(parameters)
        if project_id != self.current_project_id:
            self.set_current_project(project_id)
            self.parent.OnProject()

    def _on_current_session(self, parameters):
        session_id = int(parameters)
        if session_id != self.current_session_id:
            self.set_current_session(session_id)

    def message_handler(self, message):
        """
        Message handler for received messages.

        :param message: Received message.
        :type message: String

        """
        message_routine = {
            'mouse_event': State._on_mouse_event,
            'mouse_move': State._on_mouse_move,
            'key': State._on_key,
            'url': State._on_url,
            'open': self._on_open,
            'wx_image': self._on_wx_image,
            'new_responsive': self._on_new_responsive,
            'event': self._on_event,
            'remote_start': self._on_remote_start,
            'remote_end': self._on_remote_end,
            'set': self._on_set,
            'screenshot': self._on_screenshot,
            'current_activity': self._on_current_activity,
            'current_project': self._on_current_project,
            'current_session': self._on_current_session
        }
        LOGGER.debug('ZMQ PUBSUB Message: ' + message)
        try:
            cmd, parameters = message.split(';', 1)
            if cmd in message_routine:
                message_routine[cmd](parameters)
        except Exception as excp:
            log_msg = 'Exception in MessageHandler: {exception!s}'
            log_msg = log_msg.format(exception=excp)
            LOGGER.exception(log_msg)

    def on_project_selected(self):
        """
        Docstring.

        """
        if not self.current_project:
            return
        update = controller.add_or_update_activity
        controller.init_sync_project_directory(self.current_project_id)
        self.activity = update(self.current_project_id, diwavars.PGM_GROUP,
                               self.current_session_id, self.activity)
        self.swnp_send('SYS', 'current_activity;{0}'.format(self.activity))

    def on_session_changed(self, desired_state):
        """
        Docstring.

        """
        update = controller.add_or_update_activity
        if desired_state:
            session_id = self.start_new_session()
            if session_id < 1:
                raise SessionChangeException()
            self.activity = update(self.current_project_id, diwavars.PGM_GROUP,
                                   session_id, self.activity)
        else:
            self.end_current_session()
            self.activity = update(self.current_project_id, diwavars.PGM_GROUP,
                                   0, self.activity)
        send_session = 'current_session;{0}'.format(self.current_session_id)
        send_activity = 'current_activity;{0}'.format(self.activity)
        self.swnp_send('SYS', send_session)
        self.swnp_send('SYS', send_activity)

    def remove_observer(self):
        """
        Docstring.

        """
        if self.project_observer is not None:
            self.project_observer.unschedule_all()
            self.project_observer.stop()
            self.project_observer = None

    def set_current_session(self, session_id):
        """
        Set current session.

        :param session_id: a session id from database.
        :type session_id: Integer

        """
        session_id = int(session_id)
        if session_id > 0 and session_id != self.current_session_id:
            if self.current_session_id:
                controller.end_session(self.current_session_id)
                self.end_current_session()
            self.current_session_id = session_id
            if self.is_responsive:
                self.start_current_session_thread()
            self.parent.EnableSessionButton()
            LOGGER.info('Session %d started', int(session_id))
        elif session_id == 0 and session_id != self.current_session_id:
            print 'Current Session 0'
            self.current_session = None
            self.current_session_id = 0
            self.end_current_session()
            LOGGER.info('Session ended')

    def set_current_project(self, project_id):
        """
        Start current project loop.

        :param project_id: The project id from database.
        :type project_id: Integer

        """
        project_id = int(project_id)
        project = Project.get_by_id(project_id)
        if project is None:
            self.current_project_id = 0
            self.current_project = None
            self.set_current_session(0)
            self.remove_observer()
        elif project and self.current_project_id != project_id:
            self.current_project_id = project_id
            self.current_project = project
            extra = ' (responsive)' if self.is_responsive else ''
            log_msg = 'Project "{name}" selected{extra}'
            log_msg = log_msg.format(name=project.name, extra=extra)
            LOGGER.info(log_msg)
            self.worker.remove_all_registry_entries()
            self.worker.add_project_registry_entry('*')
            self.worker.add_project_registry_entry('Folder')
            utils.MapNetworkShare('W:', project.dir)
            if self.is_responsive:
                LOGGER.debug('Starting observers.')
                try:
                    self.set_observer()
                except (ValueError, IOError, OSError) as excp:
                    log_msg = 'self.set_observer() raised: {exception!s}'
                    log_msg = log_msg.format(exception=excp)
                    LOGGER.exception(log_msg)
            LOGGER.info('Project set to %s (%s)', project_id, project.name)

    def set_responsive(self):
        """ Docstring. """
        LOGGER.debug('Set Responsive')
        diwavars.update_responsive(diwavars.PGM_GROUP)
        self.start_current_project_thread()
        self.is_responsive = True
        self.start_current_session_thread()

    def set_observer(self):
        """
        Set an observer for file changes in project directory and
        and observer for image uploads by camera in scan folder.

        """
        LOGGER.debug('Set observers')
        if self.current_project is not None:
            self.remove_observer()
            self.project_observer = Observer(timeout=5)
            event_handler = controller.PROJECT_EVENT_HANDLER
            handle_project = event_handler(self.current_project_id, 'project')
            handle_scanner = event_handler(self.current_project_id, 'scanner')
            path_project = self.current_project.dir
            path_scanner = r'\\' + os.path.join(diwavars.STORAGE, 'Pictures')
            self.project_observer.schedule(handle_project, path_project, True)
            self.project_observer.schedule(handle_scanner, path_scanner, True)
            self.project_observer.start()
        self.is_responsive = True
        self.swnp.set_responsive('responsive')

    def start_current_project_thread(self):
        """
        Start current project loop.

        """
        if not self.current_project_thread.isAlive():
            self.current_project_thread = threads.CURRENT_PROJECT(self.swnp)
            self.current_project_thread.start()
        elif self.current_project_thread.stop_is_set():
            begin = datetime.now()
            max_delta = timedelta(seconds=5)
            while self.current_project_thread.isAlive():
                if datetime.now() - begin > max_delta:
                    raise threads.TimeoutException('Timed out!')
            self.current_project_thread = threads.CURRENT_PROJECT(self.swnp)
            self.current_project_thread.start()

    def start_current_session_thread(self):
        """
        Start current project loop.

        """
        if not self.current_session_thread.isAlive():
            self.current_session_thread = threads.CURRENT_SESSION(self.swnp)
            self.current_session_thread.start()
        elif self.current_session_thread.stop_is_set():
            begin = datetime.now()
            max_delta = timedelta(seconds=5)
            while self.current_session_thread.isAlive():
                if datetime.now() - begin > max_delta:
                    raise threads.TimeoutException('Timed out!')
            self.current_session_thread = threads.CURRENT_SESSION(self.swnp)
            self.current_session_thread.start()

    def start_new_session(self):
        """
        Start a new session.

        """
        if self.current_project is None:
            return 0
        self.end_current_session()
        #:TODO: When should previous session be passed?
        session = controller.start_new_session(self.current_project_id)
        self.current_session = session
        self.current_session_id = session.id
        self.start_current_session_thread()
        return session.id if session else 0

    def start_audio_recorder(self):
        """ Starts the audio recorder thread. """
        try:
            self.audio_recorder.start()
        except Exception as excp:
            logmsg = 'Starting audio recorder exception: %s'
            LOGGER.exception(logmsg, str(excp))

    def stop_responsive(self):
        """ Docstring. """
        diwavars.update_responsive(0)
        self.remove_observer()
        self.end_current_project()
        self.end_current_session()

    def swnp_send(self, node, message):
        """
        Sends a message to the node.

        :param node: The node for which to send a message.
        :type node: String

        :param message: The message.
        :type message: String

        """
        try:
            self.swnp.send(str(node), 'MSG', message)
        except Exception:
            LOGGER.exception('SwnpSend exception %s to %s', message, node)
