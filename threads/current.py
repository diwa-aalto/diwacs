"""
Created on 27.6.2013

:author: neriksso

"""
# Standard imports.
from time import sleep

# Own imports.
import controller
import diwavars
import threads.common
from threads.diwathread import DIWA_THREAD


def _logger():
    """
    Get the current logger for threads package.

    This function has been prefixed with _ to hide it from
    documentation as this is only used internally in the
    package.

    :returns: The logger.
    :rtype: logging.Logger

    """
    return threads.common.LOGGER


class CURRENT_PROJECT(DIWA_THREAD):
    """
    Thread for transmitting current project selection.
    When user selects a project, an instance is started.
    When a new selection is made, by any DiWaCS instance,
    the old instance is terminated.

    :param project_id: Project id from the database.
    :type project_id: Integer

    :param swnp: SWNP instance for sending data to the network.
    :type swnp: :class:`swnp.SWNP`

    """
    def __init__(self, swnp):
        DIWA_THREAD.__init__(self, name='current project')
        self.swnp = swnp

    def run(self):
        """
        Starts the thread.

        """
        # Uses iteration as count, this way we can still only send the
        # message every fifth second but check for stop flag every second.
        iteration = 0
        while not self._stop.isSet():
            iteration += 1
            if iteration >= 5:
                iteration = 0
                ipgm = diwavars.PGM_GROUP
                project_id = controller.get_active_project(ipgm)
                if project_id:
                    self.swnp('SYS', 'current_project;{0}'.format(project_id))
            sleep(1)


class CURRENT_SESSION(DIWA_THREAD):
    """
    Thread for transmitting current session id, when one is started by
    the user.  When the session is ended, by any DiWaCS instance, the
    instance is terminated.

    :param session_id: Session id from the database.
    :type session_id: Integer

    :param swnp: SWNP instance for sending data to the network.
    :type swnp: :py:class:`swnp.SWNP`

    """
    def __init__(self, swnp):
        DIWA_THREAD.__init__(self, name='current session')
        self.swnp = swnp

    def run(self):
        """
        Starts the thread.

        """
        # Uses iteration as count, this way we can still only send the
        # message every fifth second but check for stop flag every second.
        iteration = 0
        while not self._stop.isSet():
            iteration += 1
            if iteration >= 5:
                ipgm = diwavars.PGM_GROUP
                session_id = controller.get_active_session(ipgm)
                if session_id:
                    self.swnp('SYS', 'current_session;{0}'.format(session_id))
            sleep(1)
