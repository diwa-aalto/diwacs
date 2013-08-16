"""
Created on 5.6.2012

:author: neriksso
:requires: Requires ZeroMQ
:synopsis: Used to send a file to another node.

"""
import sys
import zmq


def main():
    """
    Main function of the sub program.

    Sub program is meant to be bound to windows explorer context menu.
    Context menu allows the user to quickly send files without interacting
    with DiWaCS directly.

    Transmits the send_to command to DiWaCS via interprocess connection.

    :argument node_id: ID of the node to send the file to.
    :type node_id: Integer

    :argument filepath: Path of the file to be sent.
    :type filepath: String

    :returns: windows success code (0 on success).
    :rtype: Integer

    """
    if len(sys.argv) == 3:
        try:
            node_id = sys.argv[1]
            filepath = sys.argv[2]
            context = zmq.Context()
            socket = context.socket(zmq.REQ)
            socket.setsockopt(zmq.LINGER, 5000)
            socket.connect("tcp://127.0.0.1:5555")
            command = u'send_to;' + unicode(node_id) + ';' + unicode(filepath)
            socket.send(command)
            socket.close()
            return 0
        except zmq.ZMQError:
            pass
    return 1

if __name__ == '__main__':
    sys.exit(main())
