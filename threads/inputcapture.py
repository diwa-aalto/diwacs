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


def set_capture(value):
    """
    Set's the capture value for threads.

    :param value: Is the capture on.
    :type value: Boolean

    """
    global CAPTURE
    CAPTURE = value


def logger():
    """ Get the common logger. """
    return threads.common.LOGGER


class MOUSE_CAPTURE(DIWA_THREAD):
    """
    Docstring.

    """
    def __init__(self, parent, swnp):
        DIWA_THREAD.__init__(self, target=self.parse_mouse_events,
                             name='ParseMouseEvents')
        self.parent = parent
        self.swnp = swnp
        self.pos_x = -1
        self.pos_y = -1
        self.queue = deque()

    def parse_mouse_events(self):
        """
        Docstring here.

        """
        while not self._stop.is_set():
            if len(self.queue) > 0:
                event = self.queue.popleft()
                if event.Message == 0x200:
                    if self.pos_x == False and self.pos_y == False:
                        self.pos_x = event.Position[0]
                        self.pos_y = event.Position[1]
                    else:
                        dif_x = event.Position[0] - self.pos_x
                        dif_y = event.Position[1] - self.pos_y
                        self.pos_x = event.Position[0]
                        self.pos_y = event.Position[1]
                        msg = 'mouse_move;%d,%d' % (dif_x, dif_y)
                        for id_ in self.parent.selected_nodes:
                            self.swnp(id_, msg)
                else:
                    msg = 'mouse_event;%d,%d' % (int(event.Message),
                                                 int(event.Wheel))
                    for id_ in self.parent.selected_nodes:
                        self.swnp(id_, msg)


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
        self.windowskeydown = False
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
        if self.hookmanager:
            if hasattr(self.hookmanager, 'keyboard_hook'):
                self.hookmanager.UnhookKeyboard()
            if hasattr(self.hookmanager, 'mouse_hook'):
                self.hookmanager.UnhookMouse()
        self.mouse_thread.queue.clear()
        self.reset_mouse_events()
        self.windowskeydown = False

    def hook(self):
        """
        Docstring here.

        """
        self.mouse_thread.queue.clear()
        self.reset_mouse_events()
        self.hookmanager.HookKeyboard()
        self.hookmanager.HookMouse()
        self.windowskeydown = False

    def reset_mouse_events(self):
        """
        Docstring here.

        """
        self.mouse_thread.pos_x = False
        self.mouse_thread.pos_y = False

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
            logger().exception('MouseEventCatch exception')
        # return True to pass the event to other handlers
        return not CAPTURE

    def on_keyboard_event(self, event):
        """
        Called when keyboard events are received.

        """
        key = event.KeyID
        if CAPTURE:
            if key == diwavars.KEY and self.windowskeydown:
                logger().debug('ESCAPE - CAPTURE')
                set_capture(False)
                self.reset_mouse_events()
                for id_ in self.parent.selected_nodes:
                    self.swnp(id_, 'key;%d,%d,%d' % (WM_KEYUP,
                                                     diwavars.KEY_MODIFIER,
                                                     diwavars.KEY_MODIFIER))
                    self.swnp(id_, 'remote_end;%s' % self.parent.swnp.node.id)
                del self.parent.selected_nodes[:]
                self.parent.overlay.Hide()
                self.unhook()
                return False
            #send key + KeyID
            if key == diwavars.KEY_MODIFIER:
                if event.Message == WM_KEYDOWN:
                    self.windowskeydown = True
                elif event.Message == WM_KEYUP:
                    self.windowskeydown = False
            for id_ in self.parent.selected_nodes:
                self.swnp(id_, 'key;%d,%d,%d' % (event.Message,
                                                 event.KeyID,
                                                 event.ScanCode))
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