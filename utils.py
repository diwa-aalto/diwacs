"""
Created on 17.5.2013

:author: neriksso

"""
# System imports.
import base64
import hashlib
from logging import config, getLogger
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
from models import Project


LOGGER = None


def __init_logger():
    """
    Used to initialize the logger, when running from diwacs.py

    """
    global LOGGER
    config.fileConfig('logging.conf')
    LOGGER = getLogger('utils')


def __set_logger_level(level):
    """
    Docstring here.

    """
    if LOGGER:
        LOGGER.setLevel(level)


diwavars.add_logger_initializer(__init_logger)
diwavars.add_logger_level_setter(__set_logger_level)


def get_encrypted_directory_name(name, hashed_password):
    """
    Returns the encrypted name for project directory.

    """
    if not hashed_password or len(hashed_password) < 1:
        return name
    sha = hashlib.sha256()
    sha.update(name + hashed_password)
    digest = sha.digest()
    digest = base64.b32encode(digest)
    return digest.replace('=', '') if digest else hashed_password


def hash_password(password):
    """
    Hashes the provided password.

    """
    if not password:
        return ''
    sha = hashlib.sha1()
    sha.update(diwavars.PASSWORD_SALT + password)
    for i in xrange(diwavars.PASSWORD_ITERATIONS):
        password = sha.hexdigest()
        sha = hashlib.sha1()
        hashform = '%d%s%d%s%d'
        hashform = hashform % (i, diwavars.PASSWORD_SALT, i, password, i)
        sha.update(hashform)
    result = sha.hexdigest()
    # LOGGER.debug('PASSWD: %s' % result)
    return result


def check_project_password(project_id, password):
    """
    Compares the the provided password with the project password.

    """
    try:
        project_pwd = Project.get_by_id(project_id).password
        hs = hash_password(password)
        return project_pwd == hs
    except Exception as excp:
        LOGGER.debug('CheckPassword exception: %s' % str(excp))
        return False


def IterIsLast(iterable):
    """
    IterIsLast(iterable) -> generates (item, islast) pairs.

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
    :type ip: String

    """
    try:
        c = wmi.WMI()
        for interface in c.Win32_NetworkAdapterConfiguration(IPEnabled=1):
            print interface.Description, interface.MACAddress
            for ip_address in interface.IPAddress:
                if ip_address == ip:
                    return str(interface.MACAddress).translate(None, ':')
    except Exception as excp:
        LOGGER.exception("Exception in GetMacForIp: %s", str(excp))
    return ''


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
    return octet.rstrip('.')


def MapNetworkShare(letter, share=None):
    """Maps the network share to a letter.

    :param letter: The letter for which to map.
    :type letter: String
    :param share: The network share, defaults to None which unmaps the letter.
    :type share: String

    """
    logmsg = 'error mapping share %s %s %s'
    try:
        win32wnet.WNetCancelConnection2(letter, CONNECT_UPDATE_PROFILE, 1)
    except Exception as excp:
        # NOT_CONNECTED can be safely ignored as this is the state that
        # we wished for in the beginning.
        if int(excp[0]) != ERROR_NOT_CONNECTED:
            LOGGER.exception(logmsg, letter, share, str(excp))
    # If we still need to reconnect it.
    if share is not None:
        try:
            win32wnet.WNetAddConnection2(DISK, letter, share)
        except Exception as excp:
            LOGGER.exception(logmsg, letter, share, str(excp))
