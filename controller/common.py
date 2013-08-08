"""
Created on 28.6.2013

:author: neriksso

"""
# Critical imports.
import sys
import diwavars


if diwavars.CURRENTLY_RUNNING:
    sys.stdout = open(r'data\controller_stdout.log', 'w')
    sys.stderr = open(r'data\controller_stderr.log', 'w')

# System imports.
import logging

# Third party imports.
from sqlalchemy.exc import SQLAlchemyError

# Own imports.
from models import Activity, Project, Session, Company


LOGGER = None


def __init_logger():
    """
    Used to initialize the logger, when running from diwacs.py

    """
    global LOGGER
    logging.config.fileConfig('logging.conf')
    LOGGER = logging.getLogger('controller')


def __set_logger_level(level):
    """
    Sets the logger level for controller logger.

    :param level: Level of logging.
    :type level: Integer

    """
    LOGGER.setLevel(level)


diwavars.add_logger_initializer(__init_logger)
diwavars.add_logger_level_setter(__set_logger_level)


ENGINE = None  # create_engine(DATABASE, echo=True)
NODE_NAME = ''
NODE_SCREENS = 0


def set_node_name(name):
    """
    Set the stored node name for own swnp node as global.

    :warning: This should be removed in the future as globals are bad.

    """
    global NODE_NAME
    NODE_NAME = name


def set_node_screens(screens):
    """
    Set the stored node screens settings for own swnp node as global.

    :warning: This should be removed in the future as globals are bad.

    """
    global NODE_SCREENS
    NODE_SCREENS = screens


def delete_record(record_model, id_number):
    """
    Delete a record from database

    :param record_model: The model for which to delete a record.
    :type record_model: :func:`sqlalchemy.ext.declarative.declarative_base`

    :param id_number: Recond id.
    :type id_number: Integer

    :returns: Success.
    :rtype: Boolean

    """
    try:
        instance = record_model.get_by_id(id_number)
        if isinstance(instance, Project):
            activities = Session.get('all', Activity.project_id == id_number)
            sessions = Session.get('all', Session.project_id == id_number)
            Activity.delete_many(activities)
            Session.delete_many(sessions)
        instance.delete()
        return True
    except SQLAlchemyError:
        log_msg = ('Delete record exception model {model_name!s} with '
                   'id {id_number}.')
        log_msg = log_msg.format(model_name=record_model.__name__,
                                 id_number=id_number)
        LOGGER.exception(log_msg)
        return False


def get_or_create(model, *filters, **initializers):
    """
    Fetches or creates a instance.

    :param model: The model of which an instance is wanted.
    :type model: :py:class:`sqlalchemy.ext.declarative.declarative_base`

    Filters are given after model and represent the query conditions for get.

    Initializers are given after filters and are keyword arguments used for
    initializing a new object.

    :returns: An object of the desired model.

    :throws: :py:class:`sqlalchemy.exc.SQLAlchemyException`

    """
    candidates = model.get('all', *filters)
    candidates.sort(key=model.id_ordering)
    if candidates:
        return candidates.pop()
    return model(**initializers)


def test_connection():
    """
    Test the connection to database.

    :returns: Does the software have access to the database at this time.
    :rtype: Boolean

    """
    try:
        count = Company.get('count')
        LOGGER.debug('Company count: {0}'.format(count))
        return count > 0
    except Exception as excp:
        LOGGER.exception('FAILED CONNECTION: {0!s}'.format(excp))
        return False
