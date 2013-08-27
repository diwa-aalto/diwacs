"""
Created on 17.5.2013

:author: neriksso

"""
# System imports.
import base64
import hashlib
from logging import config, getLogger
import socket

# 3rd party imports.
from win32net import NetUseAdd, NetUseDel, USE_LOTS_OF_FORCE
# from win32netcon import CONNECT_UPDATE_PROFILE, RESOURCETYPE_DISK as DISK
# import win32wnet
from winerror import ERROR_NOT_CONNECTED
import wmi

# My imports.
import diwavars


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
    Sets the logger level for utils logger.

    :param level: Level of logging.
    :type level: Integer

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
    st = [int(value) for value in dotted_ip.split('.')]
    return int('{0:02x}{1:02x}{2:02x}{3:02x}'.format(*st), 16)


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


def MapNetworkShare(letter, share=None):
    """Maps the network share to a letter.

    :param letter: The letter for which to map.
    :type letter: String
    :param share: The network share, defaults to None which unmaps the letter.
    :type share: String

    """
    logmsg = u'error mapping share {0} {1} {2!s}'
    try:
        # win32wnet.WNetCancelConnection2(letter, CONNECT_UPDATE_PROFILE, 1)
        NetUseDel(None, letter, USE_LOTS_OF_FORCE)
    except Exception as excp:
        # NOT_CONNECTED can be safely ignored as this is the state that
        # we wished for in the beginning.
        if int(excp[0]) != ERROR_NOT_CONNECTED:
            msg = logmsg.format(letter, share, excp)
            LOGGER.exception(msg.encode('utf-8'))
    # If we still need to reconnect it.
    if share is not None:
        try:
            # win32wnet.WNetAddConnection2(DISK, letter, share)
            data = {
                u'remote': unicode(share),
                u'local': unicode(letter)
            }
            NetUseAdd(None, 1, data)
        except Exception as excp:
            msg = logmsg.format(letter, share, excp)
            LOGGER.exception(msg.encode('utf-8'))
