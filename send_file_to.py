'''
Created on 5.6.2012

@author: neriksso

@requires: ZeroMQ \n

@summary: Used to send a file to another node. 
'''
import sys
import zmq

def main():
    """Main function of the sub program.
    
    Sub program is meant to be bound to windows explorer context menu.
    Context menu allows the user to quickly send files without interacting with DiWaCS directly.
    
    Transmits the send_to command to DiWaCS via interprocess connection.
    
    :argument node_id: ID of the node to send the file to.
    :type node_id: Integer
    :argument filepath: Path of the file to be sent.
    :type filepath: String
    :returns: windows success code (0 on success).
    :rtype: Integer
    """
    if len(sys.argv) == 3:
        try :
            node_id = sys.argv[1]
            filepath = sys.argv[2] 
            context = zmq.Context()     
            socket = context.socket(zmq.REQ)
            socket.connect ("tcp://127.0.0.1:5555")
            command =  'send_to;'+str(node_id)+';'+str(filepath)
            socket.send (command)
            socket.close()
            return 0
        except :
            pass
    return 1

if __name__ == '__main__':
    sys.exit(main())