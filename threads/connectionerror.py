"""
Created on 5.6.2013

:author: neriksso

"""
# Standard imports.
from collections import deque
from time import sleep

# Third party imports.
from pubsub import pub
from wx import CallAfter

# Own imports.
import threads.common
from threads.diwathread import DIWA_THREAD


def logger():
    """ Get the common logger. """
    return threads.common.LOGGER


class CONNECTION_ERROR_THREAD(DIWA_THREAD):
    """
    Thread for checking connection errors.

    :param parent: Parent object.
    :type parent: wx.Frame

    """
    def __init__(self, parent):
        DIWA_THREAD.__init__(self, name="Connection Error Checker")
        self.queue = deque()
        self.parent = parent

    def run(self):
        """
        Starts the thread.

        """
        while not self._stop.isSet():
            while len(self.queue) > 0:
                try:
                    self.queue.popleft()
                    msg = 'ConnectionErrorHandler'
                    CallAfter(pub.sendMessage, msg, error=True)
                except Exception:
                    logger().exception('Connection error checker exception')
            sleep(0.05)
