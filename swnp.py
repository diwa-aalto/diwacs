'''
Created on 30.4.2012

@author: neriksso
'''
# System imports.
from datetime import datetime, timedelta
import logging
import sys
import os
import threading
import time
import json
import random

# 3rd party imports.
from sqlalchemy import exc
import zmq
from pubsub import pub

# My imports.
import controller
import diwavars
import utils
from wos import CloseError


logging.config.fileConfig('logging.conf')
logger = logging.getLogger('swnp')

PGM_IP = "239.128.128.1:5555"
PREFIX_CHOICES = ['JOIN', 'LEAVE', 'SYNC', 'MSG', 'PING', 'PONG']
TIMEOUT = 10
PING_RATE = 2
sys.stdout = open("data\swnp_stdout.log", "wb")
sys.stderr = open("data\swnp_stderr.log", "wb")

TLDR = True


def setTLDR(value):
    global TLDR
    TLDR = value
    logger.debug('TLDR: %s' % str(value))


def SetLoggerLevel(level):
    global logger
    logger.setLevel(level)


class Node():
    """A class representation of a node in the network.

    :param id: Node id
    :type id: Integer.
    :param screens: Amount of visible screens.
    :type screens: Integer.
    :param name: The name of the node.
    :type name: String.

    """

    def __init__(self, id, screens, name=None, data=None):
        self.id = id
        self.screens = int(screens)
        self.name = name or ""
        self.data = data or ""
        self.refresh()

    def refresh(self):
        """Updates the timestamp."""
        self.timestamp = datetime.now()

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
    """A class representation of a Message.

    Messages are divided into three parts: TAG, PREFIX, PAYLOAD.
    Messages are encoded to json for transmission.

    :param TAG: TAG of the message.
    :type TAG: String.
    :param PREFIX: PREFIX of the message.
    :type PREFIX: String.
    :param PAYLOAD: PAYLOAD of the message.
    :type PAYLOAD: String.

    """

    def __init__(self, TAG, PREFIX, PAYLOAD):
        self.TAG = TAG
        if PREFIX in PREFIX_CHOICES:
            self.PREFIX = PREFIX
        else:
            raise TypeError('Invalid message type.')
        self.PAYLOAD = PAYLOAD

    def to_dict(msg):
        """Return a message in a dict.

        :param msg: The message.
        :type msg: :class:`swnp.Message`
        :rtype: Dict.

        """
        return {'TAG': msg.TAG, 'PREFIX': msg.PREFIX, 'PAYLOAD': msg.PAYLOAD}
    to_dict = staticmethod(to_dict)

    def from_json(json_dict):
        """Return a message from json.

        :param json_dict: The json.
        :type json_dict: json.
        :rtype: :class:`swnp.Message`.

        """
        return Message(json_dict['TAG'].encode('utf-8'),
                       json_dict['PREFIX'].encode('utf-8'),
                       json_dict['PAYLOAD'].encode('utf-8'))
    from_json = staticmethod(from_json)

    def __str__(self):
        return "_".join([self.TAG, self.PREFIX, self.PAYLOAD])

    def __repr__(self):
        return "_".join([self.TAG, self.PREFIX, self.PAYLOAD])


def testStorageConnection():
    return os.path.exists('\\\\' + diwavars.STORAGE + '\\Projects')


class SWNP:
    """The main class of swnp.

    This class has the required ZeroMQ bindings and is responsible for
    communicating with other instances.

    .. warning:: Only one instance per computer

    :param screens: The number of visible screens. Defaults to 0.
    :type screens: Integer.
    :param name: The name of the instance. Optional.
    :type name: String.

    """
    NODE_LIST = set()
    MSG_BUFFER = []
    SYS_BUFFER = []

    def __init__(self, pgm_group, screens=0, name=None, id=None,
                 context=None, error_handler=None):
        global PGM_IP
        # Check pgm_group
        if pgm_group != 1:
            PGM_IP = "239.128.128.%d:5555" % pgm_group
        logger.debug("PGM IP %s" % PGM_IP)
        #Create context
        self.context = context if context else zmq.Context()
        #Create publisher
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher_loopback = self.context.socket(zmq.PUB)
        self.ip = utils.GetLocalIPAddress(diwavars.STORAGE)
        logger.debug(self.ip)
        if id:
            self.id = id
        elif self.ip:
            self.id = self.ip.split('.')[3]
        else:
            self.id = random.randint(1, 154)
        self.node = Node(self.id, int(screens), name)
        #prevent overflow slow subscribers
        xvers = zmq.zmq_version_info()[0]
        logger.debug('ZMQ Major version: ' + str(xvers))
        hwm = zmq.SNDHWM if xvers > 2 else zmq.HWM
        self.publisher.setsockopt(zmq.LINGER, 0)
        self.publisher.setsockopt(hwm, 5)
        self.publisher.setsockopt(zmq.RATE, 1000000)
        self.publisher_loopback.setsockopt(hwm, 50)
        #bind publisher
        self.tladdr = "epgm://" + self.ip + ";" + PGM_IP
        self.ipraddr = "inproc://mcast_loopback"
        self.publisher.bind(self.tladdr)
        self.publisher_loopback.bind(self.ipraddr)
        #Subscriber threads
        self.sub_thread = self.StartSubRoutine(None, self.sub_routine,
                                               "Sub thread",
                                               ([self.tladdr, self.ipraddr],
                                                self.context,))
        """self.sub_thread = threading.Thread(target=self.sub_routine,
                                           name="Sub_thread",
                                           args=(tladdr, self.context,)
                                           )
        self.sub_thread.daemon = True
        self.sub_thread.start()"""
        self.sub_thread_sys = self.StartSubRoutine(None,
                                                   self.sub_routine_sys,
                                                   "Sub sys thread",
                                                   (
                                                    [self.tladdr, self.ipraddr]
                                                    , self.context,
                                                    ))
        """self.sub_thread_sys = threading.Thread(target=self.sub_routine_sys,
                                               name="Sub sys thread",
                                               args=(tladdr, self.context,)
                                               )
        self.sub_thread_sys.daemon = True
        self.sub_thread_sys.start()"""
        logger.debug('Bound listeners on: %s', str(self.tladdr))

        self.send("SYS", PREFIX_CHOICES[0], ("%s_SCREENS_%d_NAME_%s_DATA_%s" %
                                             (self.node.id, self.node.screens,
                                              self.node.name, self.node.data)
                                            )
                  )
        self.last_joined = self.id
        self.NODE_LIST.add(self.node)
        self.do_ping()
        #heartbeat
        self.ping_stop = threading.Event()
        self.ping_thread = threading.Thread(target=self.ping_routine,
                                            name="Ping thread",
                                            args=(error_handler,)
                                            )
        self.ping_thread.daemon = True
        self.ping_thread.start()
        self.timeout_stop = threading.Event()
        self.timeout_thread = threading.Thread(target=self.timeout_routine,
                                               name="timeout thread")
        self.timeout_thread.daemon = True
        self.timeout_thread.start()

    def StartSubRoutine(self, target, routine, name, args):
        if isinstance(target, threading.Thread) and target and target.isAlive():
            return
        target = threading.Thread(target=routine, name=name, args=args)
        target.daemon = True
        target.start()
        logger.debug("%s started"%name)
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
                    if not node == self.node and (
                            datetime.now() - node.timestamp > timeout):
                        to_be_removed.append(node)
                for node in to_be_removed:
                    self.NODE_LIST.discard(node)
                if len(to_be_removed) > 0:
                    pub.sendMessage("update_screens", update=True)
            except Exception, e:
                logger.exception('Timeout Exception: %s', str(e))
            """
            if self.sub_thread_sys and not self.sub_thread_sys.isAlive():
                logger.debug("Restarting sub thread sys")
                setTLDR(True)
                self.sub_thread_sys = self.StartSubRoutine(self.sub_thread_sys,
                                                           self.sub_routine_sys,
                                                           "Sub sys thread",
                                                           ([self.tladdr,
                                                             self.ipraddr],
                                                            self.context,))
            if self.sub_thread and not self.sub_thread.isAlive():
                logger.debug("Restarting sub thread")
                self.sub_thread = self.StartSubRoutine(self.sub_thread,
                                                       self.sub_routine,
                                                       "Sub thread",
                                                       ([self.tladdr,
                                                         self.ipraddr],
                                                        self.context,))
            """
            time.sleep(TIMEOUT)

    def do_ping(self):
        """Send a PING message to the network."""
        try:
            self.send("SYS", PREFIX_CHOICES[4],
                      "%s_SCREENS_%d_NAME_%s_DATA_%s" %
                      (self.id, int(self.node.screens),
                       self.node.name, self.node.data)
                      )
        except Exception, e:
            logger.exception('do_ping exception: %s', str(e))

    def ping_routine(self, error_handler):
        """A routine for sending PING messages at regular intervals."""
        logger.debug("Ping routine initializing...")
        try:
            c = controller.AddComputer(self.node.name, self.ip, self.id)
        except:
            logger.exception("Ping routine exception")
            c = None
        error = False
        logger.debug("Ping routine started")
        while not self.ping_stop.isSet():
            # Read envelope with address
            try:
                self.do_ping()
                self.node.refresh()
                if c:
                    c.screens = self.node.screens
                    controller.RefreshComputer(c)
                error = False
                time.sleep(PING_RATE)
            except (exc.OperationalError, exc.DBAPIError):
                    if not error:
                        error = True
                        error_handler.queue.put(CloseError)
            except Exception, e:
                logger.exception('Ping_routine exception: %s', str(e))
        logger.debug("Ping routine closed")

    def sub_routine(self, sub_urls, unused_context):
        """Subscriber routine for the node ID.

        :param sub_url: Subscribing URL.
        :type sub_url: String
        :param context: ZeroMQ context for message sending
        :type context: :class:`zmq.core.context.Context`

        """
        # Socket to talk to dispatcher
        global TLDR
        subscribers = []
        for i, sub_url in enumerate(sub_urls):
            subscribers.append(self.context.socket(zmq.SUB))
            if (sub_url.startswith('pgm') or sub_url.startswith('epgm')):
                subscribers[i].setsockopt(zmq.RATE, 1000000)
            subscribers[i].setsockopt(zmq.LINGER, 0)
            subscribers[i].setsockopt(zmq.SUBSCRIBE, self.id)
            subscribers[i].connect(sub_url)
        logger.debug('Listener Active!')
        while TLDR:
            # Read envelope with address
            for s in subscribers:
                try:
                    [unused_address, contents] = s.recv_multipart(zmq.NOBLOCK)
                    msg_obj = json.loads(contents,
                                         object_hook=Message.from_json)
                    """
                    logger.debug('Received: %s;%s' % (msg_obj.PREFIX,
                                                      msg_obj.PAYLOAD))
                    """
                    if (msg_obj.PAYLOAD == self.id and
                            msg_obj.PREFIX == 'LEAVE'):
                        logger.debug('LEAVE msg catched')
                        TLDR = False
                        break
                    if msg_obj.PREFIX == 'SYNC':
                        self.sync_handler(msg_obj)
                    if msg_obj.PREFIX == 'MSG':
                        pub.sendMessage("message_received",
                                        message=msg_obj.PAYLOAD)
                except zmq.Again, e:
                    # Non-blocking mode was requested and no messages
                    # are available at the moment.
                    pass
                except ValueError:
                    logger.debug('ValueError')
                    pass
                except SystemExit:
                    TLDR = False
                    logger.debug('SystemExit')
                    break
                except zmq.ContextTerminated, e:
                    # context associated with the specified
                    # socket was terminated.
                    TLDR = False
                    logger.debug('ContextTerminated: %s' % str(e))
                    break
                except zmq.ZMQError, e:
                    logger.exception("ZMQerror sub routine:%s", str(e))
                    TLDR = False
                    break
                except Exception, e:
                    logger.exception("SWNP EXCEPTION: %s", str(e))
        logger.debug('Closing sub')
        (subscriber.close() for subscriber in subscribers)

    def set_screens(self, screens):
        """Sets the number of screens for the instance.

        :param screens: New number of screens.
        :type screens: Integer.

        """
        self.node.screens = screens

    def sub_routine_sys(self, sub_urls, unused_context):
        """Subscriber routine for the node ID.

        :param sub_url: Subscribing URL.
        :type sub_url: String
        :param context: ZeroMQ context for message sending
        :type context: :class:`zmq.core.context.Context`

        """
        # Socket to talk to dispatcher
        global TLDR
        subscribers = []
        for i, sub_url in enumerate(sub_urls):
            subscribers.append(self.context.socket(zmq.SUB))
            if (sub_url.startswith('pgm') or sub_url.startswith('epgm')):
                subscribers[i].setsockopt(zmq.RATE, 1000000)
            subscribers[i].setsockopt(zmq.LINGER, 0)
            subscribers[i].setsockopt(zmq.SUBSCRIBE, "SYS")
            subscribers[i].connect(sub_url)
        logger.debug('SYS-listener active')
        while TLDR:
            # Read envelope with address.
            for s in subscribers:
                try:
                    [unused_address, contents] = s.recv_multipart(zmq.NOBLOCK)
                    msg_obj = json.loads(contents,
                                         object_hook=Message.from_json)
                    """
                    logger.debug('SYS-Received: %s;%s' %
                                 (msg_obj.PREFIX, msg_obj.PAYLOAD))
                    """
                    if (msg_obj.PREFIX == 'LEAVE' and
                            msg_obj.PAYLOAD == self.id):
                        TLDR = False
                        break
                    self.sys_handler(msg_obj)
                except ValueError:
                    pass
                except SystemExit:
                    TLDR = False
                    break
                except zmq.Again, e:
                    # Non-blocking mode was requested and no messages
                    # are available at the moment.
                    pass
                except zmq.ContextTerminated, e:
                    # context associated with the specified
                    # socket was terminated.
                    TLDR = False
                    break
                except zmq.ZMQError, e:
                    logger.exception("ZMQerror sub routine sys:%s", str(e))
                    TLDR = False
                    break
                except Exception, e:
                    logger.exception("SWNP_SYS EXCEPTION: %s", str(e))
                    TLDR = False
                    break
        logger.debug('Closing sys sub')
        (subscriber.close() for subscriber in subscribers)

    def shutdown(self):
        """shuts down all connections, no exit."""
        global TLDR
        i = 0
        limit = 5
        while self.sub_thread_sys.isAlive() and i < limit:
            self.send("SYS", PREFIX_CHOICES[1], self.id)
            time.sleep(1)
            i += 1
        i = 0
        while self.sub_thread.isAlive() and i < limit:
            self.send(self.id, PREFIX_CHOICES[1], self.id)
            time.sleep(1)
            i += 1
        self.publisher.close()
        self.publisher_loopback.close()
        TLDR = False
        if not self.context.closed:
            self.context.term()

    def close(self):
        """Closes all connections and exits."""
        global TLDR
        self.ping_stop.set()
        self.timeout_stop.set()
        i = 0
        limit = 5
        logger.debug('closing threads')
        while self.sub_thread_sys.isAlive() and i < limit:
            self.send("SYS", PREFIX_CHOICES[1], self.id)
            time.sleep(1)
            i += 1
        i = 0
        logger.debug('sub_thread sys closed' + str(
                        self.sub_thread_sys.isAlive())
                    )
        while self.sub_thread.isAlive() and i < limit:
            self.send(self.id, PREFIX_CHOICES[1], self.id)
            time.sleep(1)
            i += 1
        logger.debug('sub_thread   closed' + str(self.sub_thread.isAlive()))
        TLDR = False
        try:
            self.publisher.close()
            self.publisher_loopback.close()
            logger.debug('publisher closed')
            if not self.context.closed:
                self.context.term()
            logger.debug('context terminated')
        except:
            logger.exception('swnp close exception')
        logger.debug('swnp closed completely')

    def send(self, tag, prefix, message):
        """Send a message to the network.

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
            """
            logger.debug('Sent: %s;%s' % (msg.PREFIX, msg.PAYLOAD))
            """
            try:
                myMess = [msg.TAG, json.dumps(msg, default=Message.to_dict)]
                self.publisher_loopback.send_multipart(myMess)
                self.publisher.send_multipart(myMess)
            except Exception, e:
                logger.exception('SENT EXCEPTION: %s', str(e))
        else:
            logger.debug('debug skipping msg: %s,%s,%s' % (str(tag),
                                                           str(prefix),
                                                           str(message)))

    def get_buffer(self):
        """Gets the buffered messages and returns them

        :rtype: json.

        """
        buffer_json = json.dumps(self.MSG_BUFFER, default=Message.to_dict)
        self.MSG_BUFFER[:] = []
        return buffer_json

    def get_list(self):
        """Returns a list of all nodes

        :rtype: list.

        """
        ls = []
        for node in sorted(self.NODE_LIST, key=lambda x: int(x.id)):
            ls.append(node.id)
        return ls

    def get_screen_list(self):
        """Returns a list of screens nodes.

        :rtype: list.

        """
        ls = []
        for node in sorted(self.NODE_LIST, key=lambda x: int(x.id)):
            if int(node.screens) > 0:
                ls.append(node)
        return ls

    def sys_handler(self, msg):
        """Handler for "SYS" messages.

        :param msg: The received message.
        :type msg: :class:`swnp.Message`

        """
        if msg.PREFIX == 'JOIN':
            payload = msg.PAYLOAD.split('_')
            if  payload[0] != self.id:
                self.send("SYS", PREFIX_CHOICES[4], "%s_SCREENS_%d" %
                                                    (self.id,
                                                     int(self.node.screens)
                                                     )
                         )

            self.NODE_LIST.add(Node(payload[0], int(payload[2]), payload[4],
                                    payload[6]))
            self.last_joined = payload[0]
            pub.sendMessage("update_screens", update=True)
        if msg.PREFIX == 'LEAVE':
            node = self.find_node(msg.PAYLOAD)
            if node:
                self.NODE_LIST.discard(node)
            pub.sendMessage("update_screens", update=True)
        if msg.PREFIX == 'MSG':
            pub.sendMessage("message_received", message=msg.PAYLOAD)
        if msg.PREFIX == 'PING':
            self.ping_handler(msg.PAYLOAD)

    def ping_handler(self, payload):
        """A handler for PING messages. Sends update_screens, if necessary.

        :param payload: The payload of a PING message.
        :type payload: String.

        """
        payload = payload.split('_')
        if len(payload) < 6:
            return
        ping = self.find_node(payload[0])
        new_scr = int(payload[2])
        if ping:
            if (ping.screens != new_scr or not ping.name == payload[4] or
                    not ping.data == payload[6]):
                ping.screens = new_scr
                ping.name = payload[4]
                ping.data = payload[6]
                pub.sendMessage("update_screens", update=True)
            ping.refresh()
        else:
            self.NODE_LIST.add(Node(payload[0], new_scr, payload[4],
                                    payload[6]))
            pub.sendMessage("update_screens", update=True)

    def find_node(self, node_id):
        """Search the node list for a specific node.

        :param node_id: The id of the searched node.
        :type node_id: Integer.
        :rtype: :class:`swnp.Node`

        """
        n = ''
        for node in self.NODE_LIST:
            if node and node.id == node_id:
                n = node
        return n
