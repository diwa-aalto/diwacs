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
import netifaces
from sqlalchemy import exc
import zmq
from pubsub import pub

# My imports.
import controller
import utils
from wos import CloseError


logging.config.fileConfig('logging.conf')
logger = logging.getLogger('swnp')
PGM_IP = "239.128.128.1:5555"
STORAGE = "192.168.1.10"
PREFIX_CHOICES = ['JOIN', 'LEAVE', 'SYNC', 'MSG', 'PING', 'PONG']
TIMEOUT = 10
PING_RATE = 2
sys.stdout = open("data\swnp_stdout.log", "wb")
sys.stderr = open("data\swnp_stderr.log", "wb")


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


def testIP():
    try:
        for interface in netifaces.interfaces():
            if netifaces.AF_INET in netifaces.ifaddresses(interface) and '192.168.1' in netifaces.ifaddresses(interface)[netifaces.AF_INET][0]['addr']:
                logger.debug('192.168.1 found')
                return True
        logger.debug('192.168.1 not in any ip addresses')
        return False
    except Exception, e:
        logger.exception("Unable to loop adapters: %s", e.msg)
        return True


def testStorageConnection():
    return os.path.exists('\\\\' + STORAGE + '\\Projects')


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
        #Get ip and id
        self.ip = utils.GetLocalIPAddress(STORAGE)
        logger.debug(self.ip)
        if id:
            self.id = id
        elif self.ip:
            self.id = self.ip.split('.')[3]
        else:
            self.id = random.randint(1, 154)
        self.node = Node(self.id, int(screens), name)
        #prevent overflow slow subscribers
        self.publisher.setsockopt(zmq.LINGER, 0)
        self.publisher.setsockopt(zmq.HWM, 1)
        #set swap space for publisher
        self.publisher.setsockopt(zmq.RATE, 1000000)
        #bind publisher
        self.publisher.bind("epgm://" + self.ip + ";" + PGM_IP)

        #Subscriber threads
        self.sub_thread = threading.Thread(target=self.sub_routine,
                                           name="Sub_thread", args=(
                                                "epgm://" + self.ip + ";" +
                                                PGM_IP, self.context,)
                                           )
        self.sub_thread.daemon = True
        self.sub_thread.start()
        self.sub_thread_sys = threading.Thread(target=self.sub_routine_sys,
                                               name="Sub sys thread",
                                               args=("epgm://" + self.ip +
                                                     ";" + PGM_IP,
                                                     self.context,)
                                               )
        self.sub_thread_sys.daemon = True
        self.sub_thread_sys.start()
        #join
        #time.sleep(1)
        self.send("SYS", PREFIX_CHOICES[0], ("%s_SCREENS_%d_NAME_%s_DATA_%s" %
                                             (self.node.id, self.node.screens,
                                              self.node.name, self.node.data)
                                            )
                  )
        self.last_joined = self.id
        # print self.node
        # logger.debug("Self.node before addition to node_list %s(%s)",
        # str(self.node),str(type(self.node)))
        # logger.debug('Self.node_list before addition %s',str(self.NODE_LIST))
        self.NODE_LIST.add(self.node)
        # for node in self.NODE_LIST:
        #    logger.debug('Node in list (%s)',str(type(node)))
        # logger.debug(" node_list after append : %s",str(self.NODE_LIST))
        # pub.sendMessage("update_screens",update=True)
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

    def timeout_routine(self):
        """Routine for checking node list and removing nodes with timeout."""
        #logger.debug('Timeout routine started')
        timeout = timedelta(seconds=TIMEOUT)
        #c = controller.AddComputer(self.node.name, self.ip, self.id)
        while not self.timeout_stop.isSet():
            try:
                #c.name = self.node.name
                #c.screens = self.node.screens
                #c.wos_id = self.id
                #c = controller.RefreshComputer(c)
                #logger.debug('Timeout Computer refreshed')
                #active = controller.getActiveComputers(TIMEOUT)
                #logger.debug('Timeout active computers from db: %s',
                #str(active))
                """nodes = set()
                for row in active:
                    logger.debug("Timeout active row:%s find node %s",str(row),
                    str(row[0]))
                    n = self.find_node(str(row[0]))
                    logger.debug('Timeout node: %s',str(n) if n else "None")
                    if n:
                        nodes.add(n)
                    else:
                        nodes.add(Node(str(row[0]),row[1],row[2]))
                logger.debug('Timeout nodes: %s',str(nodes))"""
                to_be_removed = []
                for node in list(self.NODE_LIST):
                    if not node == self.node and (
                            datetime.now() - node.timestamp > timeout):
                        to_be_removed.append(node)
                for node in to_be_removed:
                    self.NODE_LIST.discard(node)
                if len(to_be_removed) > 0:
                    #logger.debug('Timeout: screen update sent')
                    pub.sendMessage("update_screens", update=True)
                """logger.debug('Timeout list comparison nodelist: %s nodes: %s result: %s',str(self.NODE_LIST),str(nodes),str(self.NODE_LIST.symmetric_difference(nodes)))
                if self.NODE_LIST.symmetric_difference(nodes):
                    self.NODE_LIST = nodes
                    pub.sendMessage("update_screens",update=True)"""
            except Exception, e:
                logger.exception('Timeout Exception: %s', str(e))
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

    def sub_routine(self, sub_url, unused_context):
        """Subscriber routine for the node ID.

        :param sub_url: Subscribing URL.
        :type sub_url: String
        :param context: ZeroMQ context for message sending
        :type context: :class:`zmq.core.context.Context`

        """
        # Socket to talk to dispatcher
        self.subscriber = self.context.socket(zmq.SUB)
        self.subscriber.setsockopt(zmq.RATE, 1000000)
        self.subscriber.setsockopt(zmq.LINGER, 0)
        self.subscriber.setsockopt(zmq.SUBSCRIBE, self.id)
        self.subscriber.connect(sub_url)
        while True:
            # Read envelope with address
            try:
                [unused_address, contents] = self.subscriber.recv_multipart()
                #print("[%s] %s\n" % (address, contents))

                msg_obj = json.loads(contents, object_hook=Message.from_json)
                logger.debug('Message: %s', str(msg_obj))
                ##print "msg reveived ",msg_obj

                if msg_obj.PAYLOAD == self.id and msg_obj.PREFIX == 'LEAVE':
                    logger.debug('LEAVE msg catched')
                    break
                if msg_obj.PREFIX == 'SYNC':
                    ##print "Syncing\n"
                    self.sync_handler(msg_obj)
                if msg_obj.PREFIX == 'MSG': 
                    #print 'got msg', msg_obj
                    #self.MSG_BUFFER.append(msg_obj)
                    pub.sendMessage("message_received",
                                    message=msg_obj.PAYLOAD)
            except ValueError:
                pass
            except SystemExit:
                break
            except zmq.ZMQError, e:
                logger.exception("ZMQerror sub routine:%s", str(e))
                break

        #print "Closing routine"
        logger.debug('Closing sub')
        self.subscriber.close()

    def set_screens(self, screens):
        """Sets the number of screens for the instance.

        :param screens: New number of screens.
        :type screens: Integer.

        """
        self.node.screens = screens

    def sub_routine_sys(self, sub_url, unused_context):
        """Subscriber routine for the node ID.

        :param sub_url: Subscribing URL.
        :type sub_url: String
        :param context: ZeroMQ context for message sending
        :type context: :class:`zmq.core.context.Context`

        """
        # Socket to talk to dispatcher
        self.subscriber_sys = self.context.socket(zmq.SUB)
        self.subscriber_sys.setsockopt(zmq.SUBSCRIBE, "SYS")
        self.subscriber.setsockopt(zmq.LINGER, 0)
        self.subscriber_sys.setsockopt(zmq.RATE, 1000000)
        self.subscriber_sys.connect(sub_url)
        while True:
            try:
                # Read envelope with address
                [unused_address, contents] = (
                            self.subscriber_sys.recv_multipart()
                    )
                msg_obj = json.loads(contents, object_hook=Message.from_json)
                #logger.debug('Sys message:%s',str(msg_obj))
                if msg_obj.PREFIX == 'LEAVE' and msg_obj.PAYLOAD == self.id:
                    break
                self.sys_handler(msg_obj)
            except ValueError:
                pass
            except SystemExit:
                break
            except zmq.ZMQError, e:
                logger.exception("ZMQerror sub routine sys:%s", str(e))
                break
        #print "Closing system routine"
        logger.debug('Closing sys sub')
        self.subscriber_sys.close()

    def shutdown(self):
        """shuts down all connections, no exit."""
        #print "Close sys"
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
        self.context.term()

    def close(self):
        """Closes all connections and exits."""
        #print "Close sys"
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
        try:
            self.publisher.close()
            logger.debug('publisher closed')
            self.context.term()
            logger.debug('context terminated')
        except:
            logger.exception('swnp close exception')
        logger.debug('swnp closed completely')
        logger.debug('sub_thread :' + str(self.sub_thread.isAlive()) +
                     'sub_thread_sys :' + str(self.sub_thread_sys.isAlive()) +
                     'ping_routine :' + str(self.ping_thread.isAlive()) +
                     'timeout_thread :' + str(self.timeout_thread.isAlive())
                     )

    def send(self, tag, prefix, message):
        """Send a message to the network.

        :param tag: The tag of the message; recipient.
        :type tag: String.
        :param prefix: The prefix of the message.
        :type prefix: String.
        :param message: The payload of the message.
        :type message: String.

        """
        if tag and prefix and message:
            msg = Message(tag, prefix, message)
            self.publisher.send_multipart([msg.TAG, json.dumps(msg,
                                                    default=Message.to_dict)
                                          ])

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
        #list=['245','246']
        return ls

    def get_screen_list(self):
        """Returns a list of screens nodes.

        :rtype: list.

        """
        my_list = []
        for node in sorted(self.NODE_LIST, key=lambda x: int(x.id)):
            if int(node.screens) > 0:
                my_list.append(node)
        #list=[Node(245,1,'HardKnocks'),Node(246,1,'Iconia')]
        return my_list

    def sys_handler(self, msg):
        """Handler for "SYS" messages.

        :param msg: The received message.
        :type msg: :class:`swnp.Message`

        """
        if msg.PREFIX == 'JOIN':
            ##print "JOIN\n"
            payload = msg.PAYLOAD.split('_')
            if  payload[0] != self.id:
                #nodelist = "_".join(self.NODE_LIST)
                self.send("SYS", PREFIX_CHOICES[4], "%s_SCREENS_%d" %
                                                    (self.id,
                                                     int(self.node.screens)
                                                     )
                         )
            #if len(filter(lambda id: id == payload[0], self.NODE_LIST))==0:
            ##print "add to node_list\n"
            self.NODE_LIST.add(Node(payload[0], int(payload[2]), payload[4],
                                    payload[6]))
            self.last_joined = payload[0]
            ##print "send update_screens \n"
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
            if ping.screens != new_scr or not ping.name == payload[4] or (
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

    def sync_handler(self, msg):
        """Handler for sync messages.

        .. deprecated:: 0.2

        :param msg: The message.
        :type msg: :class:`swnp.Message`

        """
        for id_ in msg.PAYLOAD.split('_'):
            filtered_list = filter(lambda newid: newid == id_, self.NODE_LIST)
            if len(filtered_list) == 0:
                self.NODE_LIST.append(id_)
        pub.sendMessage("update_screens", update=True)
