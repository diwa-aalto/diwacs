"""
Created on 5.6.2013

:author: neriksso

"""
# Standard imports.
from collections import deque
from win32con import WM_KEYUP, WM_KEYDOWN

# Third party imports.
import pyHook
import pythoncom

# Own imports.
import diwavars
import threads.common
from threads.diwathread import DIWA_THREAD


CAPTURE = False


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


def set_capture(value):
    """
    Set's the capture value for threads.

    :param value: Is the capture on.
    :type value: Boolean

    """
    global CAPTURE
    CAPTURE = value


class MOUSE_CAPTURE(DIWA_THREAD):
    """
    Docstring.

    """
    def __init__(self, parent, swnp):
        DIWA_THREAD.__init__(self, target=self.parse_mouse_events,
                             name='ParseMouseEvents')
        self.parent = parent
        self.swnp = swnp
        self.pos_x = None
        self.pos_y = None
        self.queue = deque()

    def parse_mouse_events(self):
        """
        Docstring here.

        """
        while not self._stop.is_set():
            if len(self.queue) > 0:
                event = self.queue.popleft()
                if event.Injected:
                    continue
                if event.Message == 0x200:
                    if self.pos_x is None or self.pos_y is None:
                        self.pos_x = event.Position[0]
                        self.pos_y = event.Position[1]
                    else:
                        dif_x = event.Position[0] - self.pos_x
                        dif_y = event.Position[1] - self.pos_y
                        # self.pos_x = event.Position[0]
                        # self.pos_y = event.Position[1]
                        msg = 'mouse_move;{0},{1}'.format(dif_x, dif_y)
                        _logger().debug(msg)
                        for id_ in self.parent.selected_nodes:
                            self.swnp.send(str(id_), 'MSG', msg)
                else:
                    msg = 'mouse_event;{0},{1}'.format(event.Message,
                                                       event.Wheel)
                    for id_ in self.parent.selected_nodes:
                        self.swnp.send(str(id_), 'MSG', msg)


class INPUT_CAPTURE(DIWA_THREAD):
    """
    Thread for capturing input from mouse/keyboard.

    :param parent: Parent instance.
    :type parent: :class:`GUI`

    :param swnp: SWNP instance for sending data to the network.
    :type swnp: :class:`swnp.SWNP`

    """
    def __init__(self, parent, swnp):
        DIWA_THREAD.__init__(self, name='input capture')
        self.parent = parent
        self.swnp = swnp
        self.hookmanager = None
        self.modifierdown = False
        self.mouse_thread = MOUSE_CAPTURE(parent, swnp)
        self.mouse_thread.deamon = True

    def stop(self):
        """
        Stops the thread.

        """
        self._stop.set()
        self.unhook()
        self.mouse_thread.stop()

    def unhook(self):
        """
        Docstring here.

        """
        try:
            if self.hookmanager:
                if hasattr(self.hookmanager, 'keyboard_hook'):
                    self.hookmanager.UnhookKeyboard()
                if hasattr(self.hookmanager, 'mouse_hook'):
                    self.hookmanager.UnhookMouse()
            self.reset_mouse_events()
            self.modifierdown = False
        except Exception as excp:
            _logger().exception(str(excp))

    def hook(self):
        """
        Docstring here.

        """
        try:
            self.reset_mouse_events()
            self.hookmanager.HookKeyboard()
            self.hookmanager.HookMouse()
            self.modifierdown = False
        except Exception as excp:
            _logger().exception(str(excp))

    def reset_mouse_events(self):
        """
        Docstring here.

        """
        self.mouse_thread.pos_x = None
        self.mouse_thread.pos_y = None
        self.mouse_thread.queue.clear()

    def on_mouse_event(self, event):
        """
        Called when mouse events are received.

            - WM_MOUSEFIRST = 0x200
            - WM_MOUSEMOVE = 0x200
            - WM_LBUTTONDOWN = 0x201
            - WM_LBUTTONUP = 0x202
            - WM_LBUTTONDBLCLK = 0x203
            - WM_RBUTTONDOWN = 0x204
            - WM_RBUTTONUP = 0x205
            - WM_RBUTTONDBLCLK = 0x206
            - WM_MBUTTONDOWN = 0x207
            - WM_MBUTTONUP = 0x208
            - WM_MBUTTONDBLCLK = 0x209
            - WM_MOUSEWHEEL = 0x20A
            - WM_MOUSEHWHEEL = 0x20E

        """
        try:
            if CAPTURE:
                self.mouse_thread.queue.append(event)
        except:
            _logger().exception('MouseEventCatch exception')
        # return True to pass the event to other handlers
        return not CAPTURE

    def on_keyboard_event(self, event):
        """
        Called when keyboard events are received.

        """
        key = event.KeyID
        if CAPTURE:
            if key == diwavars.KEY and self.modifierdown:
                _logger().debug('ESCAPE - CAPTURE')
                try:
                    set_capture(False)
                    self.unhook()
                    self.parent.overlay.Hide()
                    self.reset_mouse_events()
                    for id_ in self.parent.selected_nodes:
                        msg = 'key;{0},{1},{2}'.format(WM_KEYUP,
                                                       diwavars.KEY_MODIFIER,
                                                       diwavars.KEY_MODIFIER)
                        end = 'remote_end;{0}'.format(self.swnp.node.id)
                        self.swnp.send(str(id_), 'MSG', msg)
                        self.swnp.send(str(id_), 'MSG', end)
                    self.parent.selected_nodes = []
                except Exception as excp:
                    _logger().exception(str(excp))
                return False
            #send key + KeyID
            if key == diwavars.KEY_MODIFIER:
                if event.Message == WM_KEYDOWN:
                    self.modifierdown = True
                elif event.Message == WM_KEYUP:
                    self.modifierdown = False
            msg = 'key;{0},{1},{2}'.format(event.Message, event.KeyID,
                                           event.ScanCode)
            for id_ in self.parent.selected_nodes:
                self.swnp.send(str(id_), 'MSG', msg)
            return False
        return True

    def run(self):
        """
        Starts the thread.

        """
        self.mouse_thread.start()
        # create a hook manager
        self.hookmanager = pyHook.HookManager()
        # watch for all mouse events
        self.hookmanager.KeyAll = self.on_keyboard_event
        # watch for all mouse events
        self.hookmanager.MouseAll = self.on_mouse_event
        # Process waiting messages.
        while not self._stop.is_set():
            pythoncom.PumpWaitingMessages()
        # Unhook
        self.unhook()
