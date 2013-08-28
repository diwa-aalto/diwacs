"""
Created on 5.6.2012

:platform: Windows
:synopsis: Used to add a file in the current project.
:warning: Requires ZeroMQ.
:author: neriksso



"""
import sys
import zmq


def main():
    """
    Main function of the sub program.

    Sub program is meant to be bound to windows explorer context menu.
    Context menu allows the user to quickly add files to project without
    interacting with DiWaCS directly.

    Transmits the add_file command to DiWaCS via interprocess socket.

    :argument filepath: Path of the file to be added.
    :type filepath: String

    :returns: windows success code (0 on success).
    :rtype: Integer

    """
    context = None
    socket = None
    try:
        filepath = sys.argv[1]
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 5000)
        #: Uses interprocess ZeroMQ socket to inform diwacs of the operation.
        socket.connect('tcp://127.0.0.1:5555')
        command = u'add_to_project;0;' + unicode(filepath)
        socket.send(command.encode('utf-8'))
        socket.close()
        return 0
    except (ValueError, IOError, IndexError):
        return 1
    finally:
        if (socket is not None) and hasattr(socket, 'close'):
            socket.close()
        socket = None
        if (context is not None) and hasattr(context, 'destroy'):
            context.destroy()
        context = None


if __name__ == '__main__':
    sys.exit(main())
