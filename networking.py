'''
Created on 17.5.2013

'''
# System imports.
import socket
import subprocess

# 3rd party imports.
from win32netcon import RESOURCETYPE_DISK as DISK
import win32wnet
import wmi

# My imports.
import commons


def DottedIPToInt(dotted_ip):
    """Transforms a dotted IP address to Integer.

    :param dotted_ip: The IP address.
    :type dotted_ip: String
    :returns: The IP address.
    :rtype: Integer

    """
    st = dotted_ip.split('.')
    return int("%02x%02x%02x%02x" % (int(st[0]), int(st[1]),
                                     int(st[2]), int(st[3])), 16)


def GetLANMachines(lan_ip):
    """

    :param lan_ip: Local Area Network IP.
    :type lan_ip: string
    :returns: lan machines
    :rtype: string[]

    """
    resultlist = []
    index = lan_ip.rfind('.')
    if index > -1:
        lan_space = lan_ip[0:index]
    else:
        #print "given ip is not valid"
        return resultlist
    arp_table = subprocess.Popen('arp -a', shell=True, stdout=subprocess.PIPE)
    for line in arp_table.stdout:
        if line.find(lan_ip) > -1:
            primary = True
            continue
        if not line.strip():
            primary = False
        item = line.split.split()[0]
        if (primary and line.count('.') == 3 and
                item.find(lan_space) > -1):
            resultlist.append(item)
    return resultlist


def GetLocalIPAddress(target):
    """Used to get local Internet Protocol address.

    :returns: The current IP address.
    :rtype: string

    """
    ipaddr = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((target, 8000))
        ipaddr = s.getsockname()[0]
        s.close()
    except:
        pass
    return ipaddr


def GetMacForIp(ip):
    """Returns the mac address for an local IP address.

    :param ip: IP address
    :type ip: String.

    """
    try:
        c = wmi.WMI()
        for interface in c.Win32_NetworkAdapterConfiguration(IPEnabled=1):
            print interface.Description, interface.MACAddress
            for ip_address in interface.IPAddress:
                if ip_address == ip:
                    return str(interface.MACAddress).translate(None, ':')
    except Exception, e:
        commons.logger.exception("Exception in GetMacForIp: %s", str(e))
    return None


def IntToDottedIP(intip):
    """Transforms an Integer IP address to dotted representation.

    :param intip: The IP
    :type intip: Integer
    :returns: The IP
    :rtype: string

    """
    octet = ''
    for exp in [3, 2, 1, 0]:
        octet = octet + str(intip / (256 ** exp)) + "."
        intip = intip % (256 ** exp)
    return(octet.rstrip('.'))


def MapNetworkShare(letter, share):
    """Maps the network share to a letter.

    :param letter: The letter for which to map.
    :type letter: String.
    :param share: The network share.
    :type share: String.

    """
    try:
        win32wnet.WNetCancelConnection2(letter, 1, 1)
    except Exception, e:
        commons.logger.exception("error mapping share %s %s %s", letter,
                                 share, str(e))
    try:
        win32wnet.WNetAddConnection2(DISK, letter, share)
    except Exception, e:
        commons.logger.exception("error mapping share %s %s %s", letter,
                                 share, str(e))
