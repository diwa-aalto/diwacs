"""
Created on 5.6.2013

:author: neriksso

"""
# Standard imports.
import logging

# Own imports.
import diwavars


LOGGER = None


def __init_logger():
    """
    Used to initialize the logger, when running from diwacs.py

    """
    global LOGGER
    logging.config.fileConfig('logging.conf')
    LOGGER = logging.getLogger('threads')


def __set_logger_level(level):
    """
    Used to set logger level.

    :param level: The level desired.
    :type level: Integer

    """
    LOGGER.setLevel(level)


diwavars.add_logger_initializer(__init_logger)
diwavars.add_logger_level_setter(__set_logger_level)
