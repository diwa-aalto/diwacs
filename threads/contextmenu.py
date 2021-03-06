"""
Created on 27.6.2013

:author: neriksso

"""
# Standard imports.
import webbrowser
from ast import literal_eval

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
import modelsbase
from base64 import b64decode


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
            stop_socket.setsockopt(zmq.RCVTIMEO, 200)
            stop_socket.connect('tcp://127.0.0.1:5555')
            try:
                stop_socket.send('exit;0;0')
                stop_socket.recv()
            except zmq.ZMQError:
                pass
            self._stop.set()
            stop_socket.close()
            self.socket.close()
        except Exception as excp:
            _logger().exception('ERROR: {0!s}'.format(excp))
        _logger().debug('CMFH closed')

    def __on_send_to(self, id_, param):
        """ Send to handler. """
        try:
            param = param.decode('utf-8')
            fpath = unicode(self.handle_file([param]))
            self.send_file(id_, 'open;' + fpath.encode('utf-8'))
        except Exception as excp:
            _logger().exception('File send exception: {0!s}'.format(excp))
        return 'OK'

    def __on_add_to_project(self, id_, param):
        """ Add to Project handler. """
        id_ = id_
        param = param.decode('utf-8')
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
            event_id = controller.get_latest_event_id()
            timer = threading.Timer(diwavars.WINDOW_TAIL * 1000,
                                    self.parent.audio_recorder.save,
                                    event_id,
                                    project.dir)
            timer.start()
            CallAfter(self.parent.status_text.SetLabel, 'Recording...')
        return 'OK'

    def __on_open(self, id_, param):
        """ Open handler. """
        id_ = id_
        param = param.decode('utf-8')
        _logger().debug(u'OPEN FILE: {0}'.format(param))
        target = literal_eval(param)
        for tar in target:
            _logger().debug(u'Target: {0}'.format(tar))
        project_id = self.parent.diwa_state.current_project_id
        session_id = self.parent.diwa_state.current_session_id
        if not session_id:
            return 'OK'
        for filepath in target:
            action_id = modelsbase.REVERSE_ACTIONS['Opened']
            controller.create_file_action(filepath, action_id, session_id,
                                          project_id)
            filesystem.open_file(filepath)
        return 'OK'

    def __on_chat_message(self, id_, param):
        """ Chat message handler. """
        id_ = id_
        try:
            param = b64decode(param).decode('utf-8')
            (user, msg) = param.split(u':', 1)
            self.parent.trayicon.ShowNotification(user, msg)
        except Exception as excp:
            _logger().exception('CHATMSG_EXCEPTION: {0!s}'.format(excp))
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
        if self.parent.diwa_state.swnp.node.screens > 0:
            project = self.parent.diwa_state.current_project
            if project is None:
                return 'OK'
            node_id = self.parent.diwa_state.swnp.node.id
            filesystem.screen_capture(project.dir, node_id)
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
        if int(diwavars.RUN_CMD) == 1 and 'format' not in param:
            os.system(param)
        return 'OK'

    def run(self):
        """
        Starts the thread.

        """

        _logger().debug('CMFH INITIALIZED')
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
                _logger().debug('CMFH got message: {0!s}'.format(message))
                cmd, id_, path = message.split(';')
                if cmd in handlers:
                    self.socket.send(handlers[cmd](id_, path))
                else:
                    self.socket.send('ERROR')
                    _logger().debug('CMFH: Unknown command "{0}"'.format(cmd))
            except zmq.Again:
                pass
            except (zmq.ZMQError, zmq.ContextTerminated, SystemExit) as excp:
                # context terminated
                _logger().exception('CMFH exception: {0!s}'.format(excp))
            except Exception as excp:
                log_msg = 'Generic Exception in CMFH: {0!s}'
                _logger().exception(log_msg.format(excp))
                self.socket.send('ERROR')
