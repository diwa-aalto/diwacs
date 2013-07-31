"""
Created on 27.6.2013

:author: neriksso

"""
# Standard imports.
import webbrowser

# Third party imports.
from wx import CallAfter, CloseEvent
import zmq

# Own imports.
import diwavars
import filesystem
import threads.common
from threads.diwathread import DIWA_THREAD
import controller
import threading
import os
import models


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


class ContextMenuFailure(CloseEvent):
    """ Represents a failure of CMFH initialization. """
    pass


class SEND_FILE_CONTEX_MENU_HANDLER(DIWA_THREAD):
    """
    Thread for OS context menu actions like file sending to other node.

    :param context: ZeroMQ Context for creating sockets.
    :type context: :py:class:`zmq.Context`

    :param send_file: Sends files.
    :type send_file: Function

    :param handle_file: Handles files.
    :type handle_file: Function

    """
    def __init__(self, parent, context, send_file, handle_file):
        DIWA_THREAD.__init__(self, name='CMFH')
        self.parent = parent
        self.send_file = send_file
        self.handle_file = handle_file
        self.context = context
        try:
            self.socket = context.socket(zmq.REP)
            self.socket.setsockopt(zmq.LINGER, 0)
            self.socket.bind('tcp://*:5555')
        except zmq.ZMQError:
            CallAfter(parent.OnExit, ContextMenuFailure())

    def stop(self):
        """
        Stops the thread.

        """
        _logger().debug('BEGINNING CLOSE ON CMFH')
        try:
            stop_socket = self.context.socket(zmq.REQ)
            stop_socket.setsockopt(zmq.LINGER, 0)
            stop_socket.setsockopt(zmq.RCVTIMEO, 1000)
            stop_socket.connect('tcp://127.0.0.1:5555')
            self._stop.set()
            try:
                stop_socket.send('exit;0;0', flags=zmq.NOBLOCK)
                stop_socket.recv()
            except zmq.ZMQError:
                pass
            stop_socket.close()
            self.socket.close()
        except Exception as excp:
            _logger().exception('ERROR: {0!s}'.format(excp))
        _logger().debug('CMFH closed')

    def __on_send_to(self, id_, param):
        """ Send to handler. """
        fpath = str([self.handle_file(param)])
        self.send_file(str(id_, 'open;' + fpath))
        return 'OK'

    def __on_add_to_project(self, id_, param):
        """ Add to Project handler. """
        id_ = id_
        project_id = self.parent.diwa_state.current_project_id
        if project_id:
            controller.add_file_to_project(param, project_id)
        return 'OK'

    def __on_project(self, id_, param):
        """ Project handler. """
        param = param
        self.parent.SetCurrentProject(id_)
        return 'OK'

    def __on_save_audio(self, id_, param):
        """ Save audio handler. """
        id_ = id_
        param = param
        project = self.parent.diwa_state.current_project
        if project is None:
            return 'OK'
        if self.parent.diwa_state.is_responsive and diwavars.AUDIO:
            ide = controller.get_latest_event_id()
            timer = threading.Timer(diwavars.WINDOW_TAIL * 1000,
                                    self.parent.audio_recorder.save,
                                    ide,
                                    project.path)
            timer.start()
            CallAfter(self.parent.status_text.SetLabel, 'Recording...')
        return 'OK'

    def __on_open(self, id_, param):
        """ Open handler. """
        id_ = id_
        target = eval(param)
        project_id = self.parent.diwa_state.current_project_id
        session_id = self.parent.diwa_state.current_session_id
        if not session_id:
            return 'OK'
        for filepath in target:
            action_id = models.REVERSE_ACTIONS['Opened']
            controller.create_file_action(filepath, action_id, session_id,
                                          project_id)
            filesystem.open_file(filepath)
        return 'OK'

    def __on_chat_message(self, id_, param):
        """ Chat message handler. """
        id_ = id_
        try:
            (user, msg) = param.split(':', 1)
            self.parent.trayicon.ShowNotification(user, msg)
        except Exception as excp:
            _logger().exception('CHATMSG_EXCEPTION: %s', str(excp))
        return 'OK'

    @staticmethod
    def __on_url(id_, param):
        """ URL handler. """
        id_ = id_
        webbrowser.open(param)
        return 'OK'

    def __on_screenshot(self, id_, param):
        """ Screenshot handler. """
        id_ = id_
        param = param
        if self.parent.swnp.node.screens > 0:
            project_id = self.parent.diwa_state.current_project_id
            path = controller.get_project_path(project_id)
            node_id = self.parent.swnp.node.id
            filesystem.screen_capture(path, node_id)
        return 'OK'

    def __on_exit(self, id_, param):
        """ Exit handler. """
        id_ = id_
        param = param
        self._stop.set()
        return 'OK'

    @staticmethod
    def __on_command(id_, param):
        """ Command handler. """
        # Yes 'format' not in path is really great security
        # feature...
        id_ = id_
        if diwavars.RUN_CMD and 'format' not in param:
            os.system(param)
        return 'OK'

    def run(self):
        """
        Starts the thread.

        """

        _logger().debug('CMFH INITIALIZED------------------------------')
        handlers = {
            'send_to': self.__on_send_to,
            'add_to_project': self.__on_add_to_project,
            'project': self.__on_project,
            'save_audio': self.__on_save_audio,
            'open': self.__on_open,
            'chatmsg': self.__on_chat_message,
            'url': SEND_FILE_CONTEX_MENU_HANDLER.__on_url,
            'screenshot': self.__on_screenshot,
            'exit': self.__on_exit,
            'command': SEND_FILE_CONTEX_MENU_HANDLER.__on_command
        }

        while not self._stop.isSet():
            try:
                message = self.socket.recv(zmq.NOBLOCK)
                _logger().debug('CMFH got message: %s', message)
                cmd, id_, path = message.split(';')
                if cmd in handlers:
                    self.socket.send(handlers[cmd](id_, path))
                else:
                    self.socket.send('ERROR')
                    _logger().info('CMFH: Unknown command: %s', cmd)
            except zmq.Again:
                pass
            except zmq.ZMQError as zerr:
                # context terminated so quit silently
                if zerr.strerror == 'Context was terminated':
                    break
                else:
                    _logger().exception('CMFH exception: %s', zerr.strerror)
            except Exception as excp:
                _logger().exception('Exception in CMFH: %s', str(excp))
                self.socket.send('ERROR')
        _logger().debug('CMFH DESTROYED------------------------------')
