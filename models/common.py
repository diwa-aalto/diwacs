"""
Created on 23.5.2012


:author: neriksso
:note: Requires :py:mod:`sqlalchemy`
:synopsis:
    Defines and constructs the SQL alchemy Base class.

"""
# System imports.
import logging

# Third party imports.
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Internal imports
import diwavars

# CONSTANT
BASE = declarative_base()
ENGINE = None  # create_engine(DATABASE, echo=True)
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


def connect_to_database(expire=False):
    """
    Connect to the database and return a Session object.

    :param expire: Parameter passed to session maker as expire_on_commit.
    :type expire: Boolean

    :returns: Session.
    :rtype: :py:class:`sqlalchemy.orm.session.Session`

    """
    if ENGINE is None:
        LOGGER.exception('No engine!')
        return None
    session_function = sessionmaker(bind=ENGINE, expire_on_commit=expire)
    return session_function()


def update_database():
    """
    Update the database connection engine.

    .. note::
        This only works when DB_STRING is completely defined by
        the log reader as otherwise the create_engine call would
        cause an exception.

    """
    global ENGINE
    if diwavars.DB_STRING:
        ENGINE = create_engine(diwavars.DB_STRING, echo=False)
