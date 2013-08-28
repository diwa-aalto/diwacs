"""
Created on 5.6.2013

:author: neriksso

"""
# Standard imports.
import threading

# Own imports.
import threads.common


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


class TimeoutException(Exception):
    """ Represents a thread timeout event. """
    def __init__(self, message):
        Exception.__init__(self, message)


class DIWA_THREAD(threading.Thread):
    """
    Doc string here.

    """
    thread_list = []

    def __init__(self, target=None, name=None, args=(), kwargs=None):
        threading.Thread.__init__(self, None, target, name, args, kwargs, None)
        self._stop = threading.Event()
        DIWA_THREAD.thread_list.append(self)

    @staticmethod
    def stop_all():
        """ Stop all program threads except the calling one. """
        for diwa_thread in DIWA_THREAD.thread_list:
            is_me = diwa_thread == threading.current_thread()
            is_alive = diwa_thread.isAlive()
            if is_alive and not is_me:
                _logger().debug('KillAll: {0}'.format(diwa_thread.getName()))
                diwa_thread.stop()

    def remove_self(self):
        """
        Removes self from the thread list, this should be used only when
        the thread is sure to die soon.

        """
        DIWA_THREAD.thread_list.remove(self)

    def stop(self):
        """ Stop the thread. """
        self._stop.set()

    def stop_is_set(self):
        """ Is the thread supposed to stop. """
        return self._stop.isSet()
