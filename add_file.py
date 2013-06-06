"""
Created on 5.6.2012

.. moduleauthor:: neriksso

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
    if len(sys.argv) == 2:
        try:
            filepath = sys.argv[1]
            context = zmq.Context()
            socket = context.socket(zmq.REQ)
            #: Uses interprocess ZeroMQ socket to inform of the operation.
            socket.connect("tcp://127.0.0.1:5555")
            command = 'add_to_project;0;' + str(filepath)
            socket.send(command)
            socket.close()
            return 0
        except:
            pass
    return 1


if __name__ == '__main__':
    sys.exit(main())
