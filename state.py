"""
Created on 4.7.2013

.. moduleauthor:: neriksso
:author: neriksso

"""
# Standard imports.
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
import diwavars
import filesystem
import graphicaldesign
import macro
import swnp
import threads
import utils
from dialogs import show_modal_and_destroy


LOGGER = None


def __init_logger():
    """
    Used to initialize the logger, when running from diwacs.py

    """
    global LOGGER
    config.fileConfig('logging.conf')
    LOGGER = getLogger('state')


def __set_logger_level(level):
    """
    Sets the logger level for guitemplates logger.

    :param level: Level of logging.
    :type level: Integer

    """
    LOGGER.setLevel(level)


diwavars.add_logger_initializer(__init_logger)
diwavars.add_logger_level_setter(__set_logger_level)


def initialization_test():
    """ Docstring. """
    error = ''
    if not error and not controller.test_connection():
        error += 'Database connection failed.\n'
    if error:
        error += 'Press OK to exit.'
        LOGGER.debug(error)
        return error
    return False


def create_config():
    """
    Creates a config file.

    """
    try:
        os.makedirs(os.path.dirname(diwavars.CONFIG_PATH))
    except (os.error, IOError):
        pass
    shutil.copy('config.ini', diwavars.CONFIG_PATH)


def load_config():
    """
    Loads a config file or creates one.

    """
    if not os.path.exists(diwavars.CONFIG_PATH):
        create_config()
    return configobj.ConfigObj(diwavars.CONFIG_PATH)


class State(object):
    """
    classdocs

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
        self.worker = threads.WORKER_THREAD(self)
        self.swnp = None
        self.config_was_created = False
        try:
            # Parse the config.
            self.config_was_created = not os.path.exists(diwavars.CONFIG_PATH)
            diwavars.set_config(load_config())
            self.worker.parse_config(diwavars.CONFIG)
            screens = int(diwavars.CONFIG['SCREENS'])
            name = diwavars.CONFIG['NAME']
            node_id = ('observer' if self.is_responsive else '')
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
        ipgm = diwavars.PGM_GROUP
        self.activity = None
        self.project_folder_observer = None
        self.scan_observer = None
        self.selected_nodes = controller.get_active_activity(ipgm)
        self.current_project_id = 0
        self.current_session_id = 0
        self.controlled = None
        self.controlling = None

    def initialize(self):
        """ Docstring. """
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
            LOGGER.exception('State.initialize exception: %s', str(excp))

    def destroy(self):
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
        """ Docstring. """
        total_len = 0
        total_copied = 0
        filecount = len(src_dst_list)
        for (src, dst) in src_dst_list:
            dst = dst
            total_len += os.path.getsize(src)
        do_updates = False
        if total_len >= State.DEF_SIZE or filecount >= State.DEF_FILES:
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
        i = 1
        first_transaction = True
        lastupdate = datetime.now()
        for (src, dst) in src_dst_list:
            curlen = os.path.getsize(src)
            curcopied = 0
            fin = open(src, 'rb')
            fout = open(dst, 'wb')
            while curcopied < curlen:
                to_copy = min(State.DEF_BUFFER, curlen - curcopied)
                cstr = fin.read(to_copy)
                fout.write(cstr)
                curcopied += len(cstr)
                mydelta = (datetime.now() - lastupdate).total_seconds()
                condition = (first_transaction or mydelta > 1.0 or
                             curcopied == curlen)
                if do_updates and condition:
                    lastupdate = datetime.now()
                    first_transaction = False
                    tprc = (100.0 * float(total_copied + curcopied) /
                            float(total_len))
                    cprc = (100.0 * float(curcopied) / float(curlen))
                    bname = os.path.basename(src)
                    msg_format = '%s %d%% complete (file %d out of %d)'
                    msg = msg_format % (bname, int(cprc), i, filecount)
                    title = 'Sending items... %d%% Complete' % int(tprc)
                    dialog.SetTitle(title)
                    dialog.Update(int(tprc), msg)
            fin.close()
            fout.close()
            shutil.copystat(src, dst)
            total_copied += curlen
            self.parent.Update()
            i += 1
            first_transaction = True
            if do_updates and total_copied >= total_len:
                dialog.Update(100, '%s complete' % os.path.basename(src))

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
        proj = controller.get_project_path(self.current_project_id)
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
                res = os.path.join(proj, os.path.basename(filename))
                LOGGER.debug('Project target: %s', res)
                mydirs.append(res)
                returnvalue.append(res)
                # os.mkdir(returnvalue)
                for (currentroot, dirs, files) in os.walk(copyroot, True):
                    relativeroot = ''
                    if len(currentroot) > cidx:
                        relativeroot = currentroot[cidx:]
                    targetroot = os.path.join(proj, os.path.basename(filename),
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
                path_ = os.path.join(proj, os.path.basename(filename))
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
            src_dst_list = [(src, dst.replace(proj, tmp))
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
        LOGGER.debug('end_current_session...')
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
        # nodes = [node for node in nodes if node.id <= 10]
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

    def message_handler(self, message):
        """
        Message handler for received messages.

        :param message: Received message.
        :type message: an instance of :class:`swnp.Message`

        """
        #: TODO: Check message param type...
        try:
            LOGGER.debug('ZMQ PUBSUB Message:' + str(message))
            csid, cpid = (self.current_session_id, self.current_project_id)
            cmd, target = message.split(';', 1)
            if cmd == 'open':
                #  Open all files in list.
                target = eval(target)
                for filename in target:
                    LOGGER.info('opening file: %s', os.path.basename(filename))
                    if os.path.exists(filename):
                        if csid:
                            controller.create_file_action(filename, 6, csid,
                                                          cpid)
                        filesystem.open_file(filename)
            elif cmd == 'wx_image':
                try:
                    image_data = b64decode(target)
                    image_buffer = cStringIO.StringIO(image_data)
                    wx_image = wx.EmptyImage()
                    wx_image.LoadStream(image_buffer)
                    if wx_image.Ok():
                        graphicaldesign.ImageViewer(self.parent, wx_image)
                    else:
                        LOGGER.exception('Received invalid wx_image.')
                    wx_image = None
                except (ValueError, IOError) as excp:
                    LOGGER.exception('Receive wx_image exception: %s',
                                     str(excp))
            elif cmd == 'new_responsive':
                if self.is_responsive:
                    self.stop_responsive()
                    self.is_responsive = False
                    self.responsive = target
                    LOGGER.info('Responsive changed to: %s', str(target))
            elif cmd == 'event':
                LOGGER.info('event: %s', str(target))
                if self.is_responsive:
                    self.worker.create_event(target)
            elif cmd == 'key':
                evt_code, key, scan = target.split(',')
                evt_code = int(evt_code)
                flags = 0
                if evt_code == 257:
                    flags = 2
                macro.send_input('k', int(key), flags, int(scan))
            elif cmd == 'remote_start':
                macro.release_all_keys()
                self.controlled = target
                LOGGER.debug('CONTROLLED: %s', str(target))
            elif cmd == 'remote_end':
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
            elif cmd == 'mouse_move':
                pos_x, pos_y = target.split(',')
                input_data = [int(pos_x), int(pos_y)]
                macro.send_input('m', input_data, 0x0001)
            elif cmd == 'mouse_event':
                target, wheel = target.split(',')
                (target, wheel) = (int(target), int(wheel))
                flags = 0
                mouse_data = 0
                if target in State.TARGET_TO_FLAG:
                    flags = State.TARGET_TO_FLAG[target]
                if target in [0x20A, 0x20E]:
                    mouse_data = wheel * 120
                macro.send_input('m', [0, 0], flags, 0, mouse_data)
            elif cmd == 'url':
                LOGGER.debug('Open URL: %s', str(target))
                webbrowser.open(target)
            elif cmd == 'set' and target == 'responsive':
                if not diwavars.RESPONSIVE == 0:
                    self.is_responsive = True
                    self.set_responsive()
            elif cmd == 'screenshot':
                if self.swnp.node.screens > 0:
                    pid = self.current_project_id
                    LOGGER.info('Taking a screenshot.')
                    project_path = controller.get_project_path(pid)
                    filesystem.screen_capture(project_path, self.swnp.node.id)
            elif cmd == 'current_session':
                target = int(target)
                if self.current_session_id != target:
                    self.set_current_session(target)
            elif cmd == 'current_project':
                target = int(target)
                if cpid != target:
                    self.set_current_project(target)
                    self.parent.OnProject()
            elif cmd == 'current_activity':
                self.activity = target
                old_project_id = self.current_project_id
                pid = controller.get_project_id_by_activity(self.activity)
                sid = controller.get_session_id_by_activity(self.activity)
                if old_project_id != pid:
                    self.set_current_project(pid)
                self.set_current_session(sid)
                if old_project_id != pid:
                    self.parent.OnProject()
        except Exception as excp:
            LOGGER.exception('Exception in MessageHandler: %s', str(excp))

    def on_project_selected(self):
        """ Docstring. """
        if not self.current_project:
            return
        controller.init_sync_project_directory(self.current_project_id)
        self.activity = controller.add_activity(self.current_project_id,
                                                diwavars.PGM_GROUP,
                                                self.current_session_id,
                                                self.activity)
        self.swnp_send('SYS', 'current_activity;%s' % str(self.activity))

    def remove_observers(self):
        """ Docstring. """
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
                self.start_current_session()
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
        project = controller.get_project(project_id)
        if not project or project_id < 1:
            self.current_project_id = 0
            self.current_project = None
            self.set_current_session(0)
            if self.scan_observer:
                self.scan_observer.unschedule_all()
                self.scan_observer.stop()
            if self.project_folder_observer:
                self.project_folder_observer.unschedule_all()
                self.project_folder_observer.stop()
        elif project and self.current_project_id != project_id:
            self.current_project_id = project_id
            self.current_project = project
            LOGGER.info('Project name is %s%s', project.name,
                        ' (responsive)' if self.is_responsive else '')
            self.worker.remove_all_registry_entries()
            self.worker.add_project_registry_entry('*')
            self.worker.add_project_registry_entry('Folder')
            LOGGER.debug("setting project path")
            project_path = controller.get_project_path(project_id)
            utils.MapNetworkShare('W:', project_path)
            if self.is_responsive:
                LOGGER.debug("Starting observers.")
                self.set_observers()
            LOGGER.info('Project set to %s (%s)', project_id, project.name)

    def set_responsive(self):
        """ Docstring. """
        LOGGER.debug('Set Responsive')
        diwavars.update_responsive(diwavars.PGM_GROUP)
        self.start_current_project()
        self.is_responsive = True
        self.start_current_session()

    def set_observers(self):
        """ Docstring. """
        LOGGER.debug('Set observers')
        self.set_scan_observer()
        self.set_project_observer()

    def set_project_observer(self):
        """
        Observer for file changes in project directory.

        """
        try:
            if self.current_project_id:
                try:
                    if self.project_folder_observer:
                        self.project_folder_observer.stop()
                        del self.project_folder_observer
                except NameError:
                    pass
                LOGGER.debug('Initialize observer!')
                self.project_folder_observer = Observer()
                #: TODO: Debug if this is actually initialized sometimes.
                file_event_handler = controller.PROJECT_FILE_EVENT_HANDLER
                pfevthandler = file_event_handler(self.current_project_id)
                ppath = controller.get_project_path(self.current_project_id)
                self.project_folder_observer.schedule(pfevthandler, path=ppath,
                                                      recursive=True)
                LOGGER.debug('Starting observer for file-events now...')
                self.project_folder_observer.start()
            self.is_responsive = True
            self.swnp.set_responsive('responsive')
        except Exception as excp:
            self.is_responsive = False
            self.swnp.set_responsive('')
            LOGGER.exception('Error setting PROJECT observer: %s', str(excp))

    def set_scan_observer(self):
        """
        Observer for created files in scanned or taken with camera.

        """
        try:
            LOGGER.debug("Setting scan observer")
            if self.scan_observer:
                try:
                    self.scan_observer.stop()
                    self.scan_observer = None
                except NameError:
                    pass
            self.scan_observer = Observer()
            path = r'\\' + diwavars.STORAGE + r'\Pictures'
            shandler = controller.SCAN_HANDLER(self.current_project_id)
            self.scan_observer.schedule(shandler, path=path, recursive=True)
            self.scan_observer.start()
            self.is_responsive = True
            self.swnp.set_responsive('responsive')
        except Exception as excp:
            self.is_responsive = False
            self.swnp.set_responsive('')
            LOGGER.exception('Error setting scan observer: %s', str(excp))

    def start_current_project(self):
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

    def start_current_session(self):
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
        session = controller.start_new_session(self.current_project_id)
        self.current_session = session
        self.current_session_id = session.id
        self.start_current_session()
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
        self.remove_observers()
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
            self.swnp.send(node, 'MSG', message)
        except Exception:
            LOGGER.exception('SwnpSend exception %s to %s', message, node)
