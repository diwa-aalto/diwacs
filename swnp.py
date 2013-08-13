"""
Created on 30.4.2012

:author: neriksso

"""
# Critical imports.
import sys
import diwavars


if diwavars.CURRENTLY_RUNNING:
    sys.stdout = open(r'data\swnp_stdout.log', 'w')
    sys.stderr = open(r'data\swnp_stderr.log', 'w')


# Standard imports.
from datetime import datetime, timedelta
from logging import config, getLogger
import threading
from time import sleep
from json import dumps, loads
import random

# 3rd party imports.
from pubsub import pub
import zmq
#=========================================================================
# from zmq import (Context, LINGER, NOBLOCK, PUB, RATE, SUB, SUBSCRIBE,
#                  zmq_version_info)
# zmq_major = zmq_version_info()[0]
# if zmq_major > 2:
#     from zmq import SNDHWM  # @UnresolvedImport
# else:
#     from zmq import HWM  # @UnresolvedImport
#=========================================================================


# My imports.
import controller
import utils
from dialogs import CloseError
from zmq.error import Again, ContextTerminated, ZMQError


LOGGER = None


def __init_logger():
    """
    Used to initialize the logger, when running from diwacs.py

    """
    global LOGGER
    config.fileConfig('logging.conf')
    LOGGER = getLogger('swnp')


def __set_logger_level(level):
    """
    Sets the logger level for swnp logger.

    :param level: Level of logging.
    :type level: Integer

    """
    LOGGER.setLevel(level)


diwavars.add_logger_initializer(__init_logger)
diwavars.add_logger_level_setter(__set_logger_level)


PREFIX_CHOICES = ['JOIN', 'LEAVE', 'SYNC', 'MSG', 'PING', 'PONG']
TIMEOUT = 10
PING_RATE = 3


class Node():
    """
    A class representation of a node in the network.

    :param node_id: Node id.
    :type node_id: Integer

    :param screens: Amount of visible screens.
    :type screens: Integer

    :param name: The name of the node.
    :type name: String

    """
    def __init__(self, node_id, screens, name=None, data=None):
        self.id = node_id
        self.screens = int(screens)
        self.name = name or ''
        self.data = data or ''
        self.timestamp = datetime.now()

    def refresh(self):
        """
        Updates the timestamp.

        """
        self.timestamp = datetime.now()

    def get_age(self):
        """ Return the elapsed time since last refresh. """
        return (datetime.now() - self.timestamp)

    def __str__(self):
        return "%s: %s with %s screens data %s" % (self.id, self.name,
                                                   self.screens, self.data)

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return int(self.id)

    def __cmp__(self, other):
        return cmp(self.id, other.id)


class Message():
    """
    A class representation of a Message.

    Messages are divided into three parts: tag, prefix, payload.
    Messages are encoded to json for transmission.

    :param tag: tag of the message.
    :type tag: String

    :param prefix: prefix of the message.
    :type prefix: String

    :param payload: payload of the message.
    :type payload: String

    """
    def __init__(self, tag, prefix, payload):
        self.tag = tag
        if prefix in PREFIX_CHOICES:
            self.prefix = prefix
        else:
            raise TypeError('Invalid message type: %s' % prefix)
        self.payload = payload

    def to_dict(msg):
        """
        Return a message in a dict.

        :param msg: The message.
        :type msg: :class:`swnp.Message`

        :returns: Dictionary representation of the message.
        :rtype: Dict

        """
        return {'TAG': msg.tag, 'PREFIX': msg.prefix, 'PAYLOAD': msg.payload}
    to_dict = staticmethod(to_dict)

    def from_json(json_dict):
        """
        Return a message from json.

        :param json_dict: The json.
        :type json_dict: json

        :returns: Initializes a message from JSON object.
        :rtype: :py:class:`swnp.Message`.

        """
        return Message(json_dict['TAG'].encode('utf-8'),
                       json_dict['PREFIX'].encode('utf-8'),
                       json_dict['PAYLOAD'].encode('utf-8'))
    from_json = staticmethod(from_json)

    def __str__(self):
        return '_'.join([self.tag, self.prefix, self.payload])

    def __repr__(self):
        return '_'.join([self.tag, self.prefix, self.payload])


class SWNP:
    """
    The main class of swnp.

    This class has the required ZeroMQ bindings and is responsible for
    communicating with other instances.

    .. warning:: Only one instance per computer

    :param pgm_group: The Multicast Group this node wants to be a part of.
    :type pgm_group: Integer

    :param screens: The number of visible screens. Defaults to 0.
    :type screens: Integer

    :param name: The name of the instance.
    :type name: String

    :param node_id: ID of the current instance.
    :type node_id: Integer

    :param context: ZeroMQ context to use.
    :type context: :py:class:`zmq.Context`

    :param error_handler: Error handler for the init constructor.
    :type error_handler: :py:class:`wos.CONN_ERR_TH`

    """
    NODE_LIST = set()
    MSG_BUFFER = []
    SYS_BUFFER = []

    def __init__(self, pgm_group, screens=0, name=None, node_id=None,
                 context=None, error_handler=None):
        # Check pgm_group
        if not pgm_group:
            pgm_group = 1
        pgm_ip = '239.128.128.%d:5555' % pgm_group
        LOGGER.debug('PGM IP %s', pgm_ip)

        #Create context
        self.context = context if context else zmq.Context()
        self.context.setsockopt(zmq.LINGER, 0)  # Set default linger value.

        #Create publisher
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher_loopback = self.context.socket(zmq.PUB)
        self.ip = utils.GetLocalIPAddress(diwavars.STORAGE)
        LOGGER.info('Own IP: %s', self.ip)
        if node_id:
            self.id = node_id
        elif self.ip:
            self.id = self.ip.split('.')[3]
        else:
            self.id = random.randint(1, 154)
        self.node = Node(int(self.id), int(screens), name)
        self.online = True

        # Prevent overflowing slow subscribers
        self.publisher.setsockopt(zmq.LINGER, 0)
        self.publisher.setsockopt(zmq.RATE, 1000000)
        self.publisher.set_hwm(5)
        self.publisher_loopback.setsockopt(zmq.LINGER, 0)
        self.publisher_loopback.set_hwm(50)

        # Bind publisher
        self.tladdr = 'epgm://' + self.ip + ';' + pgm_ip
        self.ipraddr = 'inproc://mcast_loopback'
        self.publisher.bind(self.tladdr)
        self.publisher_loopback.bind(self.ipraddr)
        # Subscriber threads
        targs = ([self.tladdr, self.ipraddr], )
        self.sub_thread = SWNP.start_sub_routine(None, self.sub_routine,
                                                 'Sub thread', targs)
        self.sub_thread_sys = SWNP.start_sub_routine(None,
                                                     self.sub_routine_sys,
                                                     'Sub sys thread', targs)
        LOGGER.debug('Bound listeners on: %s', str(self.tladdr))

        join_str = '{id}_SCREENS_{screens}_NAME_{name}_DATA_{data}'
        join_str = join_str.format(**self.node.__dict__)
        self.send('SYS', PREFIX_CHOICES[0], join_str)
        self.last_joined = self.id
        self.NODE_LIST.add(self.node)
        self.do_ping()

        #heartbeat
        self.ping_stop = threading.Event()
        self.ping_thread = threading.Thread(
            target=self.ping_routine,
            name='Ping thread',
            args=(error_handler,)
        )
        self.ping_thread.daemon = True
        self.ping_thread.start()
        self.timeout_stop = threading.Event()
        self.timeout_thread = threading.Thread(target=self.timeout_routine,
                                               name='timeout thread')
        self.timeout_thread.daemon = True
        self.timeout_thread.start()

    @staticmethod
    def start_sub_routine(target, routine, name, args):
        """
        A wrapper for starting up subroutine threads.

        :param target: Variable that contains the current thread for routine.
        :type target: :py:class:`threading.Thread`

        :param routine: The routine to run.

        :param name: Name of the routine.
        :type name: String

        :param args: Arguments for the routine.
        :type args: List

        :returns: The thread of subroutine.
        :rtype: :py:class:`threading.Thread`

        """
        target_is_thread = isinstance(target, threading.Thread)
        if (target_is_thread and target and target.isAlive()):
            return
        target = threading.Thread(target=routine, name=name, args=args)
        target.daemon = True
        target.start()
        LOGGER.debug('%s started', name)
        return target

    def timeout_routine(self):
        """
        Routine for checking node list and removing nodes with timeout.

        """
        timeout = timedelta(seconds=TIMEOUT)
        while not self.timeout_stop.isSet():
            try:
                to_be_removed = []
                for node in list(self.NODE_LIST):
                    if node != self.node and node.get_age() > timeout:
                        to_be_removed.append(node)
                for node in to_be_removed:
                    # TODO: Remove controlled if true.
                    self.NODE_LIST.discard(node)
                if len(to_be_removed) > 0:
                    pub.sendMessage('update_screens', update=True)
            except Exception as excp:
                LOGGER.exception('Timeout Exception: %s', str(excp))
            sleep(TIMEOUT)

    def do_ping(self):
        """
        Send a PING message to the network.

        """
        try:
            msg_format = '%s_SCREENS_%d_NAME_%s_DATA_%s'
            msg = msg_format % (self.id, int(self.node.screens),
                                self.node.name, self.node.data)
            self.send('SYS', PREFIX_CHOICES[4], msg)
        except ZMQError as excp:
            LOGGER.exception('do_ping exception: %s', str(excp))

    def ping_routine(self, error_handler):
        """
        A routine for sending PING messages at regular intervals.

        """
        LOGGER.debug('Ping routine initializing...')
        comp = None
        try:
            comp = controller.add_computer(self.node.name, self.ip, self.id)
        except Exception as excp:
            LOGGER.exception('Ping routine exception: %s', str(excp))
        previous_success = False
        LOGGER.debug('Ping routine started.')
        # Ping every 100th step and sleep for PING_RATE / 100...
        step = 0
        while self.online and not self.ping_stop.isSet():
            # Read envelope with address
            step += 1
            if step == 50:
                try:
                    self.do_ping()
                    self.node.refresh()
                    if comp:
                        comp.screens = self.node.screens
                        success = controller.refresh_computer(comp)
                        if not success and previous_success:
                            error_handler.queue.append(CloseError)
                        previous_success = success
                except Exception as excp:
                    LOGGER.exception('Ping_routine exception: %s', str(excp))
            step = step % 50
            sleep(PING_RATE / 50.0)
        LOGGER.debug('Ping routine closed.')
        error_handler.stop()

    def sub_routine(self, sub_urls):
        """
        Subscriber routine for the node ID.

        :param sub_urls: Subscribing URLs.
        :type sub_urls: List of Strings

        """
        subscribers = []
        for i, sub_url in enumerate(sub_urls):
            subscribers.append(self.context.socket(zmq.SUB))
            if (sub_url.startswith('pgm') or sub_url.startswith('epgm')):
                subscribers[i].setsockopt(zmq.RATE, 1000000)
            subscribers[i].setsockopt(zmq.LINGER, 0)
            subscribers[i].setsockopt(zmq.SUBSCRIBE, self.id)
            subscribers[i].connect(sub_url)
        LOGGER.debug('Listener Active!')
        while self.online:
            for s in subscribers:
                try:
                    (address, contents) = s.recv_multipart(zmq.NOBLOCK)
                    message = loads(contents, object_hook=Message.from_json)
                    (prefix, payload) = (message.prefix, message.payload)
                    if payload == self.id and prefix == 'LEAVE':
                        LOGGER.debug('LEAVE msg catched')
                        sleep(0.1)
                        self.online = False
                        break
                    elif prefix == 'SYNC':
                        LOGGER.exception('DEPRECATED METHOD USED!!!')
                        # self.sync_handler(message)
                    elif prefix == 'MSG':
                        pub.sendMessage('message_received', message=payload)
                except Again:
                    # Non-blocking mode was requested and no messages
                    # are available at the moment.
                    pass
                except ValueError as excp:
                    LOGGER.debug('ValueError: %s - %s', str(contents),
                                 str(excp))
                except (SystemExit, ContextTerminated, ZMQError):
                    LOGGER.debug('Exit sub routine')
                    self.online = False
                    break
                except Exception as excp:
                    LOGGER.exception('SWNP EXCEPTION: %s', str(excp))
        LOGGER.debug('Closing sub')
        while len(subscribers):
            sub = subscribers.pop()
            sub.close()
            sub = None
        LOGGER.debug('Sub closed')

    def sub_routine_sys(self, sub_urls):
        """
        Subscriber routine for the node ID.

        :param sub_urls: Subscribing URLs.
        :type sub_urls: List of Strings

        """
        # Socket to talk to dispatcher
        subscribers = []
        for sub_url in sub_urls:
            sub = self.context.socket(zmq.SUB)
            if (sub_url.startswith('pgm') or sub_url.startswith('epgm')):
                sub.setsockopt(zmq.RATE, 1000000)
            sub.setsockopt(zmq.LINGER, 0)
            sub.setsockopt(zmq.SUBSCRIBE, 'SYS')
            sub.connect(sub_url)
            subscribers.append(sub)
        LOGGER.debug('SYS-listener active')
        while self.online:
            # Read envelope with address.
            for s in subscribers:
                try:
                    pack = s.recv_multipart(zmq.NOBLOCK)
                    (address, contents) = pack
                    msg_hook = Message.from_json
                    msg_obj = loads(contents, object_hook=msg_hook)
                    receiver = 0
                    try:
                        receiver = int(msg_obj.payload)
                        msg_for_self = (receiver == self.node.id)
                        if msg_obj.prefix == 'LEAVE' and msg_for_self:
                            sleep(0.1)
                            self.online = False
                            break
                    except ValueError:
                        pass
                    self.sys_handler(msg_obj)
                except Again:
                    # Non-blocking mode was requested and no messages
                    # are available at the moment or there was a parse
                    # error.
                    pass
                except ValueError as excp:
                    LOGGER.exception('ValueError!: %s', str(excp))
                    txt = '{1}{2}Unpacking: \n{0}{2}{1}'
                    xts = '\n'.join([str(p) for p in pack])
                    LOGGER.exception(txt.format(xts, '-' * 10, '\n' * 5))
                except (SystemExit, ContextTerminated):
                    # context associated with the specified
                    # socket was terminated or the app is closing.
                    LOGGER.exception('SYS-EXCPT: {0!s}'.format(excp))
                    self.online = False
                    break
                except Exception as excp:
                    LOGGER.info('SWNP MSG: %s', str(contents))
                    LOGGER.exception('SWNP_SYS EXCEPTION: %s', str(excp))
                    self.online = False
                    break
        LOGGER.debug('Closing sys sub')
        while len(subscribers):
            sub = subscribers.pop()
            sub.close()
            sub = None
        LOGGER.debug('Sys sub closed')

    def set_name(self, name):
        """
        Sets the name for the instance.

        :param name: New name of the instance.
        :type name: String

        """
        self.node.name = name
        controller.refresh_computer_by_wos_id(self.node.id, new_name=name)

    def set_screens(self, screens):
        """
        Sets the number of screens for the instance.

        :param screens: New number of screens.
        :type screens: Integer

        """
        self.node.screens = screens
        controller.refresh_computer_by_wos_id(self.node.id,
                                              new_screens=screens)

    def set_responsive(self, responsive):
        """
        Sets the responsive flag for the instance.

        :param responsive: New number of screens.
        :type responsive: Integer

        """
        self.node.data = responsive
        new_responsive = diwavars.PGM_GROUP if responsive else 0
        controller.refresh_computer_by_wos_id(self.node.id,
                                              new_responsive=new_responsive)

    def shutdown(self):
        """
        Shuts down all connections, no exit.

        """
        i = 0
        limit = 4
        alive = self.sub_thread.isAlive
        alive_sys = self.sub_thread_sys.isAlive
        while (alive() or alive_sys()) and i < limit:
            # System sub routine thread.
            if alive_sys():
                self.send('SYS', 'LEAVE', str(self.id))
            # Sub routine thread.
            if alive():
                self.send(str(self.id), 'LEAVE', str(self.id))
            sleep(0.25)
            i += 1
        self.online = False
        LOGGER.debug('Closing publishers...')
        self.publisher.close()
        self.publisher_loopback.close()
        if not self.context.closed:
            LOGGER.debug('Terminating context...')
            # NOTE: context.terminate() was replaced with this
            # because terminate used to hang even when all the sockets
            # had linger=0 option set.
            self.context = None
        else:
            LOGGER.debug('Context was already terminated...')
        LOGGER.debug('SWNP shutdown complete...')

    def close(self):
        """
        Closes all connections and exits.

        """
        LOGGER.debug('Beginning close of SWNP')
        self.ping_stop.set()
        self.timeout_stop.set()
        LOGGER.debug('Closing threads')
        try:
            self.shutdown()
        except Exception as excp:
            LOGGER.exception('Close error: %s', str(excp))
        alive_sub = str(not self.sub_thread.isAlive())
        alive_sys = str(not self.sub_thread_sys.isAlive())
        debug_format = (
            'SWNP CLOSE:\n'
            'sub_routine closed %s\n'
            'sub_routine_system closed %s\n'
            'swnp closed completely'
        )
        LOGGER.debug(debug_format, alive_sub, alive_sys)

    def send(self, tag, prefix, message):
        """
        Send a message to the network.

        :param tag: The tag of the message; recipient.
        :type tag: String

        :param prefix: The prefix of the message.
        :type prefix: String

        :param message: The payload of the message.
        :type message: String

        """
        if self.publisher.closed:
            return
        if tag and prefix and message:
            msg = Message(tag, prefix, message)
            try:
                my_message = [msg.tag, dumps(msg, default=Message.to_dict)]
                if msg.prefix != 'PING':
                    self.publisher_loopback.send_multipart(my_message)
                self.publisher.send_multipart(my_message)
            except (ZMQError, ValueError) as excp:
                LOGGER.exception('SENT EXCEPTION: %s', str(excp))

    def get_buffer(self):
        """
        Gets the buffered messages and returns them

        :returns: JSON formated string.
        :rtype: String

        """
        buffer_json = None
        try:
            buffer_json = dumps(self.MSG_BUFFER, default=Message.to_dict)
        except ValueError:
            pass
        self.MSG_BUFFER[:] = []
        return buffer_json

    def get_list(self):
        """
        Returns a list of all nodes

        :rtype: list

        """
        return sorted(self.NODE_LIST, key=lambda node: int(node.id))

    def get_screen_list(self):
        """
        Returns a list of screens nodes.

        :rtype: list.

        """
        return [node for node in self.get_list() if node.screens > 0]

    def _on_join(self, payload):
        """ On join handlers. """
        payload = payload.split('_')
        joiner_id = int(payload[0])
        joiner_screens = int(payload[2])
        joiner_name = payload[4]
        joiner_data = payload[6]
        if joiner_id != self.id:
            reply = '%s_SCREENS_%d' % (self.id, int(self.node.screens))
            self.send('SYS', PREFIX_CHOICES[4], reply)
        if self.find_node(joiner_id) is not None:
            return
        new_node = Node(joiner_id, joiner_screens, joiner_name, joiner_data)
        self.NODE_LIST.add(new_node)
        self.last_joined = joiner_id
        pub.sendMessage('update_screens', update=True)

    def _on_leave(self, payload):
        """ On leave handlers. """
        try:
            node_id = int(payload)
        except ValueError:
            return
        node = self.find_node(node_id)
        if node:
            self.NODE_LIST.discard(node)
        pub.sendMessage('update_screens', update=True)

    @staticmethod
    def _on_msg(payload):
        """ On message handlers. """
        pub.sendMessage('message_received', message=payload)

    def _on_ping(self, payload):
        """ On ping handlers. """
        self.ping_handler(payload)

    def _on_default(self, payload):
        """ On unrecognized command handlers. """
        pass

    def sys_handler(self, msg):
        """
        Handler for "SYS" messages.

        :param msg: The received message.
        :type msg: :class:`swnp.Message`

        """
        handlers = {
            'JOIN': self._on_join,
            'LEAVE': self._on_leave,
            'MSG': SWNP._on_msg,
            'PING': self._on_ping
        }
        # LOGGER.debug('SWNP: {0!s}'.format(msg))
        if msg.prefix in handlers:
            handlers[msg.prefix](msg.payload)
        else:
            self._on_default(msg.payload)

    def ping_handler(self, payload):
        """
        A handler for PING messages. Sends update_screens, if necessary.

        :param payload: The payload of a PING message.
        :type payload: String

        """
        payload = payload.split('_')
        if len(payload) < 6:
            return
        node_id = int(payload[0])
        new_screens = int(payload[2])
        new_name = payload[4]
        new_data = payload[6]
        target_node = self.find_node(node_id)
        if target_node is not None:
            update_node = False
            if target_node.screens != new_screens:
                target_node.screens = new_screens
                update_node = True
            if target_node.name != new_name:
                target_node.name = new_name
                update_node = True
            if target_node.data == new_data:
                target_node.data = new_data
                update_node = True
            if update_node:
                pub.sendMessage('update_screens', update=True)
            target_node.refresh()
        else:
            node = Node(node_id, new_screens, new_name, new_data)
            self.NODE_LIST.add(node)
            pub.sendMessage('update_screens', update=True)

    def find_node(self, node_id):
        """
        Search the node list for a specific node.

        :param node_id: The id of the searched node.
        :type node_id: Integer

        :rtype: :class:`swnp.Node`

        """
        result_node = None
        nodes_gen = (x for x in self.NODE_LIST if x.id == node_id)
        for node in nodes_gen:
            result_node = node
        return result_node
