'''
Created on 12.9.2012

@author: neriksso
'''
import sys
import zmq
import json
import socket
import time


def get_local_ip_address(target):
    ipaddr = ''
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((target, 8000))
        ipaddr = s.getsockname()[0]
        s.close()
    except:
        ipaddr = None
    return ipaddr


class Message:
    """A class representation of a Message.

    Messages are divided into three parts: TAG, PREFIX, PAYLOAD. Messages are
    encoded to json for transmission.

    :param TAG: TAG of the message.
    :type TAG: String.
    :param PREFIX: PREFIX of the message.
    :type PREFIX: String.
    :param PAYLOAD: PAYLOAD of the message.
    :type PAYLOAD: String.

    """
    def __init__(self, TAG, PREFIX, PAYLOAD):
        self.TAG = TAG
        self.PREFIX = PREFIX
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
        a = json_dict['TAG'].encode('utf-8')
        b = json_dict['PREFIX'].encode('utf-8')
        c = json_dict['PAYLOAD'].encode('utf-8')
        return Message(a, b, c)

    from_json = staticmethod(from_json)

    def __str__(self):
        return "_".join([self.TAG, self.PREFIX, self.PAYLOAD])

    def __repr__(self):
        return "_".join([self.TAG, self.PREFIX, self.PAYLOAD])


def main():
        if len(sys.argv) == 3:
            target = sys.argv[1]
            filepath = sys.argv[2]
            context = zmq.Context()
            socket = context.socket(zmq.PUB)
            socket.setsockopt(zmq.RATE, 1000000)
            ip = get_local_ip_address("www.google.fi")
            #print ip
            socket.bind("epgm://" + ip + ";239.128.128.2:5555")
            command = 'open;' + str(filepath)
            msg = Message(target, 'MSG', command)
            #print msg
            socket.send_multipart([msg.TAG,
                                   json.dumps(msg, default=Message.to_dict)])
            time.sleep(5)
            socket.close()
            context.term()

if __name__ == '__main__':
    main()
