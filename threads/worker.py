"""
Created on 27.6.2013

:author: neriksso

"""
# Standard imports.
import urllib2
import base64
from logging import getLevelName
from datetime import datetime
import os
from _winreg import (KEY_ALL_ACCESS, OpenKey, CloseKey, EnumKey, DeleteKey,
                     CreateKey, SetValueEx, REG_SZ, HKEY_CURRENT_USER)

# Third party imports.
import pyHook
from wx import CallLater

# Own imports.
import controller
import diwavars
import threads.common
from threads.checkupdate import CHECK_UPDATE
from threads.diwathread import DIWA_THREAD
from utils import IterIsLast
import modelsbase


def _logger():
    """
    Get the current logger for threads package.

    This function has been prefixed with _ to hide it from
    documentation as this is only used internally in the
    package.

    :returns: The logger.
    :rtype: logging.Logger

    """
    return threads.common.LOGGER


class SNAPSHOT_THREAD(DIWA_THREAD):
    """
    Worker thread for taking snapshot.

    :param path: File path where to store the snapshot.
    :type path: String

    """
    def __init__(self, path):
        DIWA_THREAD.__init__(self, name='Snapshot')
        self.path = path
        self.daemon = True
        self.start()

    def run(self):
        """
        Worker procedure for storing the snapshot.

        .. warning::
            This object has a timeout of 1 minute. So consider terminating
            the thread on shutdown if it's hanging.

        """
        filepath = os.path.join(self.path, 'Snapshots')
        try:
            os.makedirs(filepath)
        except OSError:
            pass
        request = urllib2.Request(diwavars.CAMERA_URL)
        base64string = base64.encodestring('%s:%s' % (diwavars.CAMERA_USER,
                                                      diwavars.CAMERA_PASS))
        request.add_header('Authorization', 'Basic %s' % base64string.strip())
        event_id = controller.get_latest_event_id()
        try:
            data = urllib2.urlopen(request, timeout=60).read()
            datestring = datetime.now().strftime('%d%m%Y%H%M%S')
            name = str(event_id) + '_' + datestring + '.jpg'
            _logger().debug('snapshot filename: {0}'.format(name))
            with open(os.path.join(filepath, name), 'wb') as output:
                output.write(data)
        except (IOError, OSError) as excp:
            # urllib2.URLError inherits IOError so both the write
            # and URL errors are caught by this.
            _logger().exception('Snapshot exception: {0!s}'.format(excp))


#: TODO:
#    Does the execution actually happen in WORKER_THREAD when one
#    of it's methods is called?
#    If not this design is flawed and should be replaced by something
#    like: WORKER_THREAD.add_callback(target_method, **kwargs)
#
class WORKER_THREAD(DIWA_THREAD):
    """
    Worker thread for non-UI jobs.

    :param parent: The GUI object.
    :type parant: :py:class:`diwacs.GraphicalUserInterface`

    """
    _version_checker = None

    def __init__(self, parent):
        DIWA_THREAD.__init__(self, name='CMFH')
        self.parent = parent
        self.daemon = True
        self.start()

    def check_responsive(self):
        """
        Docstring here.

        """
        state = self.parent.diwa_state
        if not state.responsive and not state.is_responsive:
            nodes = controller.get_active_responsive_nodes(diwavars.PGM_GROUP)
            log_msg = 'Active nodes: ' + ', '.join([str(n) for n in nodes])
            _logger().debug(log_msg)
            if not nodes:
                if diwavars.RESPONSIVE == diwavars.PGM_GROUP:
                    state.set_responsive()
                    _logger().debug('Setting self as responsive')
            else:
                state.responsive = str(nodes[0].wos_id)
                if state.responsive == state.swnp.node.id:
                    state.set_responsive()
        log_msg = 'Responsive checked. Current responsive is: {0}'
        _logger().debug(log_msg.format(state.responsive))

    @staticmethod
    def add_project_registry_entry(reg_type):
        """
        Adds "Add to project" context menu item to registry. The item
        will be added to Software\\Classes\\<reg_type>, where <reg_type>
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
                    SetValueEx(rkey, '', 0, REG_SZ, mypath + ' \"%1\"')
            CloseKey(rkey)

    @staticmethod
    def add_registry_entry(name, node_id):
        """
        Adds a node to registry.

        :param name: Node name.
        :type name: String

        :param id: Node id.
        :type id: Integer

        """
        keys = ['Software', 'Classes', '*', 'shell',
                'DiWaCS: Open in %s' % name, 'command']
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
                    SetValueEx(rkey, '', 0, REG_SZ, regpath)
            if rkey:
                CloseKey(rkey)

    @staticmethod
    def remove_all_registry_entries():
        """
        Removes all related registry entries.

        """
        main_key = None
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
                        except WindowsError:
                            count += 1
                    else:
                        count += 1
                except WindowsError:
                    break
        except Exception as excp:
            excp_string = 'Exception in remove_all_registry_entries: %s'
            _logger().exception(excp_string, str(excp))
        if main_key:
            CloseKey(main_key)

    @staticmethod
    def __on_storage(value):
        """ Short stub setter. """
        diwavars.update_storage(value)
        modelsbase.update_database()

    @staticmethod
    def __on_db_address(value):
        """ Short stub setter. """
        diwavars.update_database_vars(address=value)
        modelsbase.update_database()

    @staticmethod
    def __on_db_name(value):
        """ Short stub setter. """
        diwavars.update_database_vars(name=value)
        modelsbase.update_database()

    @staticmethod
    def __on_db_type(value):
        """ Short stub setter. """
        diwavars.update_database_vars(type_=value)
        modelsbase.update_database()

    @staticmethod
    def __on_db_user(value):
        """ Short stub setter. """
        diwavars.update_database_vars(user=value)
        modelsbase.update_database()

    @staticmethod
    def __on_db_pass(value):
        """ Short stub setter. """
        diwavars.update_database_vars(password=value)
        modelsbase.update_database()

    @staticmethod
    def __on_name(value):
        """ Short stub setter. """
        controller.set_node_name(value)

    @staticmethod
    def __on_screens(value):
        """ Short stub setter. """
        controller.set_node_screens(value)

    @staticmethod
    def __on_run_cmd(value):
        """ Short stub setter. """
        diwavars.set_run_cmd(value)

    @staticmethod
    def __on_remote_keys(value):
        """ Short stub setter. """
        if value.find('+'):
            value = value.split('+')
        elif value.find('-'):
            value = value.split('-')
        elif value.find(':'):
            value = value.split(':')
        elif value.find(','):
            value = value.split(',')
        else:
            value = eval(value)
        if (len(value) < 2) or (not value[0]) or (not value[1]):
            return
        value[0] = 'VK_' + value[0]
        value[1] = 'VK_' + value[1]
        vk_mod = pyHook.HookConstants.VKeyToID(value[0])
        vk_key = pyHook.HookConstants.VKeyToID(value[1])
        if (vk_mod == 0) or (vk_key == 0):
            _logger().exception('INVALID KEYCODES: %s, %s', value[0], value[1])
            return
        diwavars.update_keys(vk_mod, vk_key)

    @staticmethod
    def __on_pgm_group(value):
        """ Short stub setter. """
        diwavars.update_PGM_group(value)

    @staticmethod
    def __on_audio(parent, value):
        """ Short stub setter. """
        _logger().debug('AUDIO in config: %s', str(value))
        value = eval(value)
        if value:
            diwavars.update_audio(value)
            _logger().debug('Starting audio recorder')
            parent.diwa_state.start_audio_recorder()

    @staticmethod
    def __on_logger_level(value):
        """ Short stub setter. """
        level = getLevelName(str(value).upper())
        for setter in diwavars.LOGGER_LEVEL_SETTER_LIST:
            setter(level)

    @staticmethod
    def __on_camera_url(value):
        """ Short stub setter. """
        diwavars.update_camera_vars(str(value), None, None)

    @staticmethod
    def __on_camera_user(value):
        """ Short stub setter. """
        diwavars.update_camera_vars(None, str(value), None)

    @staticmethod
    def __on_camera_pass(value):
        """ Short stub setter. """
        diwavars.update_camera_vars(None, None, str(value))

    @staticmethod
    def __on_pad_url(value):
        """ Short stub setter. """
        diwavars.update_padfile(value)
        WORKER_THREAD._version_checker = CHECK_UPDATE()
        WORKER_THREAD._version_checker.start()

    @staticmethod
    def __on_responsive(value):
        """ Short stub setter. """
        diwavars.update_responsive(eval(value))

    def parse_config(self, config_object):
        """
        Handles config file settings.

        """
        handler = {
            'STORAGE': WORKER_THREAD.__on_storage,
            'DB_ADDRESS': WORKER_THREAD.__on_db_address,
            'DB_NAME': WORKER_THREAD.__on_db_name,
            'DB_TYPE': WORKER_THREAD.__on_db_type,
            'DB_USER': WORKER_THREAD.__on_db_user,
            'DB_PASS': WORKER_THREAD.__on_db_pass,
            'NAME': WORKER_THREAD.__on_name,
            'SCREENS': WORKER_THREAD.__on_screens,
            'RUN_CMD': WORKER_THREAD.__on_run_cmd,
            'REMOTEKEYS': WORKER_THREAD.__on_remote_keys,
            'PGM_GROUP': WORKER_THREAD.__on_pgm_group,
            'LOGGER_LEVEL': WORKER_THREAD.__on_logger_level,
            'CAMERA_URL': WORKER_THREAD.__on_camera_url,
            'CAMERA_USER': WORKER_THREAD.__on_camera_user,
            'CAMERA_PASS': WORKER_THREAD.__on_camera_pass,
            'PAD_URL': WORKER_THREAD.__on_pad_url,
            'RESPONSIVE': WORKER_THREAD.__on_responsive
        }
        for key, value in config_object.items():
            _logger().debug('(' + key + '=' + value + ')')
            if key in handler:
                handler[key](value)
            elif key == 'AUDIO':
                WORKER_THREAD.__on_audio(self.parent, value)
            else:
                globals()[key] = eval(value)

    def create_event(self, title):
        """
        Docstring here.

        """
        project = self.parent.diwa_state.current_project
        session = self.parent.diwa_state.current_session
        if (project is None) or (session is None):
            return  # TODO: Define a new exception type and catch
                    #       it in the UI design to display an
                    #       informative pop-up about project and
                    #       session.
        event_id = controller.add_event(session.id, title, '')
        SNAPSHOT_THREAD(project.path)
        try:
            self.parent.SwnpSend('SYS', 'screenshot;0')
            if diwavars.AUDIO:
                log_msg = 'Buffering audio for {0} seconds.'
                _logger().debug(log_msg.format(diwavars.WINDOW_TAIL))
                self.parent.status_text.SetLabel('Recording...')
                parameters = (event_id, project.path)
                CallLater(millis=diwavars.WINDOW_TAIL * 1000,
                          callable=self.parent.audio_recorder.save,
                          args=parameters)
        except:
            _logger().exception('Create Event exception.')

    def run(self):
        """Run the worker thread."""
        while not self._stop.isSet():
            pass
