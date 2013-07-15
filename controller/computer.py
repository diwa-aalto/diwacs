"""
Created on 28.6.2013

:author: neriksso

"""
# Critical import.
import controller.common

# Third party imports.
import pythoncom
import sqlalchemy

# Own imports.
import diwavars
from models import Computer
import utils


def logger():
    """ Return controller logger. """
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
    computer = None
    database = None
    try:
        database = controller.common.connect_to_database(True)
        setting = pythoncom.COINIT_MULTITHREADED  # pylint: disable=E1101
        pythoncom.CoInitializeEx(setting)  # pylint: disable=E1101
        wanted_mac = utils.GetMacForIp(pc_ip)
        ip_int = utils.DottedIPToInt(pc_ip)
        if wanted_mac:
            temp_pc = database.query(Computer).filter_by(mac=wanted_mac)
            temp_pc = temp_pc.order_by(sqlalchemy.desc(Computer.id)).first()
            if temp_pc:
                temp_pc.name = name
                temp_pc.ip = ip_int
                temp_pc.wos_id = wos_id
                database.add(temp_pc)
                computer = temp_pc
                database.commit()
        else:
            logger().debug('no computer instance  found')
            temp_pc = Computer(ip=ip_int, name=name, mac=wanted_mac,
                               wos_id=wos_id)
            database.add(temp_pc)
            computer = temp_pc
            database.commit()
        if computer:
            database.expunge(computer)
    except sqlalchemy.exc.SQLAlchemyError, excp:
        logger().exception('add_computer exception: %s', str(excp))
    if database:
        database.close()
    return computer


def get_active_computers(timeout):
    """
    Get all the active computers from database.

    :param timeout:
        The number of seconds an "active" computer may have been idle while
        still being considered active.
    :type timeout: Integer

    :returns: A list of active computers.
    :rtype: List of :py:class:`models.Computer`

    """
    logger().debug('get_active_computers called with timeout %d', int(timeout))
    result = []
    database = None
    if not timeout:
        return result
    try:
        database = controller.common.connect_to_database()
        diff_unit = sqlalchemy.text('second')
        my_filter = sqlalchemy.func.timestampdiff(diff_unit, Computer.time,
                                                  sqlalchemy.func.now())
        pcs = database.query(Computer)
        pcs = pcs.filter(my_filter < timeout).all()
        result = pcs
    except sqlalchemy.exc.SQLAlchemyError:
        pass
    if database:
        database.close()
    return result


def get_active_responsive_nodes(pgm_group):
    """
    Return the wos_id fields of all active responsive nodes.

    :param pgm_group: The responsive group we want.
    :type pgm_group: Integer

    :returns: A list of node IDs that are both active and responsive.
    :rtype: A list of Integer

    """
    nodes = get_active_computers(timeout=10)
    return [node.wos_id for node in nodes if node.responsive == pgm_group]


def last_active_computer():
    """
    Is the current node last active computer.

    .. note::
        This uses 10 seconds as timeout for definition "not active".

    :rtype: Boolean

    """
    return len(get_active_computers(timeout=10)) < 2


def refresh_computer(computer):
    """
    Refresh the computer in database.

    :param computer: The computer to refresh.
    :type computer: :py:class:`models.Computer`

    :returns: The Refreshed computer.
    :rtype: :py:class:`models.Computer`

    """
    database = None
    target = computer
    try:
        database = controller.common.connect_to_database()
        try:
            temp_computer = database.query(Computer)
            temp_computer = temp_computer.filter(Computer.id == computer.id)
            temp_computer = temp_computer.one()
            target = temp_computer
        except sqlalchemy.exc.SQLAlchemyError:
            pass
        target.time = sqlalchemy.func.now()
        target.responsive = diwavars.RESPONSIVE
        target.name = controller.common.NODE_NAME
        target.screens = controller.common.NODE_SCREENS
        database.add(target)
        database.commit()
        database.expunge(target)
    except sqlalchemy.exc.DBAPIError, excp:
        try:
            database.expunge(target)
        except sqlalchemy.exc.SQLAlchemyError:
            pass
        database.close()
        logger().debug('exc.DBAPIError detected: %s', str(excp))
        raise excp
    if database:
        database.close()
    return computer


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

    :returns: Success
    :rtype: Boolean

    """
    database = None
    success = False
    try:
        database = controller.common.connect_to_database()
        computer = database.query(Computer)
        computer = computer.filter(Computer.wos_id == wos_id).one()
        computer.time = sqlalchemy.func.now()
        if new_name:
            computer.name = new_name
        if new_screens:
            computer.screens = new_screens
        if new_responsive:
            computer.responsive = new_responsive
        database.add(computer)
        database.commit()
        database.expunge(computer)
    except sqlalchemy.exc.SQLAlchemyError, excp:
        success = False
        logger().debug('exc.DBAPIError detected: %s', str(excp))
    if database:
        database.close()
    return success


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

    """
    database = None
    try:
        database = controller.common.connect_to_database(True)
        comp = add_computer(name, pc_ip, wos_id)
        database.add(comp)
        session.computers.append(comp)
        database.add(session)
        database.commit()
        database.expunge(session)
        database.expunge(comp)
    except sqlalchemy.exc.SQLAlchemyError, excp:
        logger().debug('Exception in add_computer_to_session: %s', str(excp))
    if database:
        database.close()
