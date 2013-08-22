"""
Created on 28.6.2013

:author: neriksso

"""
# Critical import.
import controller.common

# Third party imports.
import pythoncom
from sqlalchemy import text, func

# Own imports.
import diwavars
from models import Computer
import utils


def _logger():
    """
    Get the current logger for controller package.

    This function has been prefixed with _ to hide it from
    documentation as this is only used internally in the
    package.

    :returns: The logger.
    :rtype: logging.Logger

    """
    return controller.common.LOGGER


def add_computer(name, pc_ip, wos_id):
    """
    Add a new computer to the database.

    :param name: Name of the computer.
    :type name: String

    :param pc_ip: IP address of the computer.
    :type pc_ip: String

    :param wos_id: Node ID of the computer (usually the last part of IP).
    :type wos_id: Integer

    :returns: The added computer
    :rtype: :py:class:`models.Computer`

    """
    setting = pythoncom.COINIT_MULTITHREADED  # pylint: disable=E1101
    pythoncom.CoInitializeEx(setting)  # pylint: disable=E1101
    pc_mac = utils.GetMacForIp(pc_ip)
    ip_int = utils.DottedIPToInt(pc_ip)
    pgm_group = diwavars.PGM_GROUP
    # Try finding computer by MAC address.
    if pc_mac:
        computer = Computer.get_most_recent_by_mac(pc_mac)
        if computer:
            computer.name = name
            computer.ip = ip_int
            computer.pgm_group = pgm_group
            computer.wos_id = wos_id
            computer.update()
            return computer
    # Try finding computer by name...
    computer = Computer.get('last', Computer.name == name)
    if computer:
        computer.ip = ip_int
        computer.mac = pc_mac
        computer.pgm_group = pgm_group
        computer.wos_id = wos_id
        computer.update()
        return computer
    # Create new...
    computer = Computer(name, ip_int, pc_mac, controller.common.NODE_SCREENS,
                        0, pgm_group, wos_id)
    return computer


def get_active_computers(timeout, *filters):
    """
    Get all the active computers from database.

    :param timeout:
        The number of seconds an "active" computer may have been idle while
        still being considered active. Default is 10 seconds.
    :type timeout: Integer

    :returns: A list of active computers.
    :rtype: List of :py:class:`models.Computer`

    """
    difference_unit = text('second')
    age_filter = func.timestampdiff(difference_unit, Computer.time, func.now())
    filters = (age_filter < timeout,
               Computer.pgm_group == diwavars.PGM_GROUP) + filters
    return Computer.get('all', *filters)


def get_active_responsive_nodes(pgm_group):
    """
    Return the wos_id fields of all active responsive nodes.

    :param pgm_group: The responsive group we want.
    :type pgm_group: Integer

    :returns: A list of node IDs that are both active and responsive.
    :rtype: A list of Integer

    """
    return get_active_computers(10, Computer.responsive == pgm_group)


def last_active_computer():
    """
    Is the current node last active computer.

    :rtype: Boolean

    """
    return len(get_active_computers(3)) < 2


def refresh_computer(computer):
    """
    Refresh the computer in database.

    :param computer: The computer to refresh.
    :type computer: :py:class:`models.Computer`

    """
    computer.time = func.now()
    computer.responsive = diwavars.RESPONSIVE
    computer.name = controller.common.NODE_NAME
    computer.screens = controller.common.NODE_SCREENS
    computer.pgm_group = diwavars.PGM_GROUP
    computer.update()


def refresh_computer_by_wos_id(wos_id, new_name=None, new_screens=None,
                               new_responsive=None):
    """
    Refresh the computer by node id and give it optionally new configurations.

    :param wos_id: The ID of the node to refresh.
    :type wos_id: Integer

    :param new_name: Optional new name for the node.
    :type new_name: String

    :param new_screens: Optional new screens configuration for the node.
    :type new_screens: Integer

    :param new_responsive: Optional new responsive setting for the node.
    :type new_responsive: Integer

    """
    computer = Computer.get('last', Computer.wos_id == wos_id)
    needs_to_update = False
    if new_name:
        needs_to_update = True
        computer.name = new_name
    if new_screens:
        needs_to_update = True
        computer.screens = new_screens
    if new_responsive:
        needs_to_update = True
        computer.responsive = new_responsive
    if needs_to_update:
        computer.update()


def add_computer_to_session(session, name, pc_ip, wos_id):
    """
    Adds a computer to a session.

    :param session: A current session.
    :type session: :class:`models.Session`

    :param name: A name of the computer.
    :type name: String

    :param pc_ip: Computers IP address.
    :type pc_ip: Integer

    :param wos_id: Wos id of the computer.
    :type wos_id: Integer

    :note:
        This is not currently used so consider removing it.

    """  # TODO: Fix and add usage.
    computer = add_computer(name, pc_ip, wos_id)
    session.computers.append(computer)
    session.update()
