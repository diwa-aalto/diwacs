'''
Created on 5.6.2012

@author: neriksso
'''
import sys
import zmq

def main():
    if len(sys.argv) == 3:
        id = sys.argv[1]
        filepath = sys.argv[2] 
        context = zmq.Context()     
        socket = context.socket(zmq.REQ)
        socket.connect ("tcp://127.0.0.1:5555")
        command =  'send_to;'+str(id)+';'+str(filepath)
        #print "sending command",command
        socket.send (command)
        socket.close()

if __name__ == '__main__':
    main()