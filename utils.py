"""
Recreated on 17.5.2013

:author: neriksso

"""
# System imports.
import base64
import hashlib
import logging
import socket
import subprocess

# 3rd party imports.
from win32netcon import CONNECT_UPDATE_PROFILE, RESOURCETYPE_DISK as DISK
import win32wnet
from winerror import ERROR_NOT_CONNECTED
import wmi

# My imports.
import controller
import diwavars
logging.config.fileConfig('logging.conf')
logger = logging.getLogger('utils')


def GetEncryptedDirName(name, hashed_password):
    """
    Returns the encrypted name for project directory.

    """
    if not hashed_password or len(hashed_password) < 1:
        return name
    m = hashlib.sha256()
    m.update(name + hashed_password)
    digest = m.digest()
    myhash = base64.b32encode(digest)
    return myhash.replace('=', '') if myhash else hashed_password


def HashPassword(password):
    """
    Hashes the provided password.

    """
    if not password:
        return ''
    m = hashlib.sha1()
    m.update(diwavars.PASSWORD_SALT + password)
    for i in xrange(diwavars.PASSWORD_ITERATIONS):
        password = m.hexdigest()
        m = hashlib.sha1()
        m.update(str(i) + diwavars.PASSWORD_SALT + str(i) + password + str(i))
    result = m.hexdigest()
    logger.debug('PASSWD: %s' % result)
    return result


def CheckProjectPassword(project_id, password):
    """
    Compares the the provided password with the project password.

    """
    return controller.GetProjectPassword(project_id) == HashPassword(password)


def IterIsLast(iterable):
    """ IterIsLast(iterable) -> generates (item, islast) pairs

    Generates pairs where the first element is an item from the iterable
    source and the second element is a boolean flag indicating if it is the
    last item in the sequence.

    :param iterable: The iterable element.
    :type iterable: iterable

    """
    it = iter(iterable)
    prev = it.next()
    for item in it:
        yield prev, False
        prev = item
    yield prev, True


def SetLoggerLevel(level):
    logger.setLevel(level)


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
        logger.exception("Exception in GetMacForIp: %s", str(e))
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


def MapNetworkShare(letter, share=None):
    """Maps the network share to a letter.

    :param letter: The letter for which to map.
    :type letter: String.
    :param share: The network share, defaults to None which unmaps the letter.
    :type share: String

    """
    try:
        win32wnet.WNetCancelConnection2(letter, CONNECT_UPDATE_PROFILE, 1)
    except Exception, e:
        if int(e[0]) != ERROR_NOT_CONNECTED:
            logger.exception("error mapping share %s %s %s", letter,
                             share, str(e))
    # Special case:
    if share is not None:
        try:
            win32wnet.WNetAddConnection2(DISK, letter, share)
        except Exception, e:
            logger.exception("error mapping share %s %s %s", letter, share,
                             str(e))
