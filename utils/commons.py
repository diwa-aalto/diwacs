'''
Created on 17.5.2013

'''
# System imports.
import hashlib
import logging
import os

# My imports.
import controller
import vars
logging.config.fileConfig(os.path.abspath('logging.conf'))
logger = logging.getLogger('utils')


def GetProjectPassword(project_id):
    project = controller.GetProject(project_id)
    m = hashlib.sha1()
    m.update(str(project.id) + project.password if project.password else '')
    return m.hexdigest()


def HashPassword(password):
    m = hashlib.sha1()
    m.update(password)
    return m.hexdigest()


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


def UpdateCameraVars(url, user, passwd):
    if url:
        vars.CAMERA_URL = url
    if user:
        vars.CAMERA_USER = user
    if passwd:
        vars.CAMERA_PASS = passwd
