"""macro.py imports a SendKeys module which may be downloaded at:
http://www.rutherfurd.net/python/sendkeys/

It also defines the following functions:

click() -- calls left mouse click
hold() -- presses and holds left mouse button
release() -- releases left mouse button

rightclick() -- calls right mouse click
righthold() -- calls right mouse hold
rightrelease() -- calls right mouse release

middleclick() -- calls middle mouse click
middlehold() -- calls middle mouse hold
middlerelease() -- calls middle mouse release


move(x, y) -- moves mouse to x/y coordinates (in pixels)

slide(x, y) -- slides mouse to x/y coodinates (in pixels)
              also supports optional speed='slow', speed='fast'

The imported SendKeys has many features, but the basics are as
follows: SendKeys("Text goes here",pause=0.5,with_spaces=True)
The first string is typed on screep with a 0.5 second pause.
with_spaces = True means to NOT ignore spaces.

SendKeys("{ENTER}",pause=0.1) ; "{ENTER}" (in curly brackets) is
not typed, but instead presses the enter button on the keyboard.

"""

# System imports.
from ctypes import (byref, c_long, c_short, c_ulong, c_ushort, POINTER,
                    pointer, sizeof, Structure, Union, windll)
import time

# 3rd party imports.
import wx


# Some module variables.
SENDKEYS_TABLE_VIRTUAL = (
    (0x08, "{BACKSPACE}"),
    (0x09, "{TAB}"),
    (0x0D, "{ENTER}"),
    (0x1B, "{ESC}"),
    (0x20, "{SPACE}"),
    (0x2E, "{DEL}"),
    (19, "{BREAK}"),
    (0x14, "{CAP}"),
    (0x23, "{END}"),
    (0x24, "{HOME}"),
    (0x25, "{LEFT}"),
    (0x26, "{UP}"),
    (0x27, "{RIGHT}"),
    (0x28, "{DOWN}"),
    (0x29, ""),
    (0x2A, "{PRTSC}"),
    (44, ""),
    (0x2C, "{INSERT}"),
    (0x2F, "{HELP}"),
    (0x60, "0"),
    (0x61, "1"),
    (0x62, "2"),
    (0x63, "3"),
    (0x64, "4"),
    (0x65, "5"),
    (0x66, "6"),
    (0x67, "7"),
    (0x68, "8"),
    (0x69, "9"),
    (0x6A, "{MULTIPLY}"),
    (0x6B, "{ADD}"),
    (0x6C, ""),
    (0x6D, "{SUBTRACT}"),
    (0x6E, ""),
    (0x6F, "{DIVIDE}"),
    (112, "{F1}"),
    (113, "{F2}"),
    (114, "{F3}"),
    (115, "{F4}"),
    (115, "{F5}"),
    (116, "{F6}"),
    (117, "{F7}"),
    (118, "{F8}"),
    (119, "{F9}"),
    (120, "{F10}"),
    (121, "{F11}"),
    (122, "{F12}"),
    (123, "{F13}"),
    (124, "{F14}"),
    (125, "{F15}"),
    (126, "{F16}"),
    (127, "{F17}"),
    (128, "{F18}"),
    (129, "{F19}"),
    (130, "{F20}"),
    (131, "{F21}"),
    (132, "{F22}"),
    (133, "{F23}"),
    (134, "{F24}"),
    (0x90, "{NUMLOCK}"),
    (145, "{SCROLLLOCK}"),
    (0x21, "{PGUP}"),
    (0x22, "{PGDN}"),
    (0xA4, "{LWIN}"),
    (0x5C, "{RWIN}"),
    (0x5B, "{LWIN}"),
    (0x5C, "{RWIN}"),
    )

SENDKEYS_TABLE = (
    (wx.WXK_BACK, "{BACKSPACE}"),
    (wx.WXK_TAB, "{TAB}"),
    (wx.WXK_RETURN, "{ENTER}"),
    (wx.WXK_ESCAPE, "{ESC}"),
    (wx.WXK_SPACE, "{SPACE}"),
    (wx.WXK_DELETE, "{DEL}"),
    (wx.WXK_START, ""),
    (wx.WXK_LBUTTON, ""),
    (wx.WXK_RBUTTON, ""),
    (wx.WXK_CANCEL, ""),
    (wx.WXK_MBUTTON, ""),
    (wx.WXK_CLEAR, ""),
    (wx.WXK_SHIFT, ""),
    (wx.WXK_ALT, ""),
    (wx.WXK_CONTROL, ""),
    (wx.WXK_MENU, ""),
    (wx.WXK_PAUSE, "{BREAK}"),
    (wx.WXK_CAPITAL, "{CAP}"),
    (wx.WXK_END, "{END}"),
    (wx.WXK_HOME, "{HOME}"),
    (wx.WXK_LEFT, "{LEFT}"),
    (wx.WXK_UP, "{UP}"),
    (wx.WXK_RIGHT, "{RIGHT}"),
    (wx.WXK_DOWN, "{DOWN}"),
    (wx.WXK_SELECT, ""),
    (wx.WXK_PRINT, "{PRTSC}"),
    (wx.WXK_EXECUTE, ""),
    (wx.WXK_SNAPSHOT, ""),
    (wx.WXK_INSERT, "{INSERT}"),
    (wx.WXK_HELP, "{HELP}"),
    (wx.WXK_NUMPAD0, "0"),
    (wx.WXK_NUMPAD1, "1"),
    (wx.WXK_NUMPAD2, "2"),
    (wx.WXK_NUMPAD3, "3"),
    (wx.WXK_NUMPAD4, "4"),
    (wx.WXK_NUMPAD5, "5"),
    (wx.WXK_NUMPAD6, "6"),
    (wx.WXK_NUMPAD7, "7"),
    (wx.WXK_NUMPAD8, "8"),
    (wx.WXK_NUMPAD9, "9"),
    (wx.WXK_MULTIPLY, "{MULTIPLY}"),
    (wx.WXK_ADD, "{ADD}"),
    (wx.WXK_SEPARATOR, ""),
    (wx.WXK_SUBTRACT, "{SUBTRACT}"),
    (wx.WXK_DECIMAL, ""),
    (wx.WXK_DIVIDE, "{DIVIDE}"),
    (wx.WXK_F1, "{F1}"),
    (wx.WXK_F2, "{F2}"),
    (wx.WXK_F3, "{F3}"),
    (wx.WXK_F4, "{F4}"),
    (wx.WXK_F5, "{F5}"),
    (wx.WXK_F6, "{F6}"),
    (wx.WXK_F7, "{F7}"),
    (wx.WXK_F8, "{F8}"),
    (wx.WXK_F9, "{F9}"),
    (wx.WXK_F10, "{F10}"),
    (wx.WXK_F11, "{F11}"),
    (wx.WXK_F12, "{F12}"),
    (wx.WXK_F13, "{F13}"),
    (wx.WXK_F14, "{F14}"),
    (wx.WXK_F15, "{F15}"),
    (wx.WXK_F16, "{F16}"),
    (wx.WXK_F17, "{F17}"),
    (wx.WXK_F18, "{F18}"),
    (wx.WXK_F19, "{F19}"),
    (wx.WXK_F20, "{F20}"),
    (wx.WXK_F21, "{F21}"),
    (wx.WXK_F22, "{F22}"),
    (wx.WXK_F23, "{F23}"),
    (wx.WXK_F24, "{F24}"),
    (wx.WXK_NUMLOCK, "{NUMLOCK}"),
    (wx.WXK_SCROLL, "{SCROLLLOCK}"),
    (wx.WXK_PAGEUP, "{PGUP}"),
    (wx.WXK_PAGEDOWN, "{PGDN}"),
    (wx.WXK_NUMPAD_SPACE, "{SPACE}"),
    (wx.WXK_NUMPAD_TAB, "{TAB}"),
    (wx.WXK_NUMPAD_ENTER, "{ENTER}"),
    (wx.WXK_NUMPAD_F1, "{F1}"),
    (wx.WXK_NUMPAD_F2, "{F2}"),
    (wx.WXK_NUMPAD_F3, "{F3}"),
    (wx.WXK_NUMPAD_F4, "{F4}"),
    (wx.WXK_NUMPAD_HOME, "{HOME}"),
    (wx.WXK_NUMPAD_LEFT, "{LEFT}"),
    (wx.WXK_NUMPAD_UP, "{UP}"),
    (wx.WXK_NUMPAD_RIGHT, "{RIGHT}"),
    (wx.WXK_NUMPAD_DOWN, "{DOWN}"),
    (wx.WXK_NUMPAD_PAGEUP, "{PGUP}"),
    (wx.WXK_NUMPAD_PAGEDOWN, "{PGDN}"),
    (wx.WXK_NUMPAD_END, "{END}"),
    (wx.WXK_NUMPAD_BEGIN, ""),
    (wx.WXK_NUMPAD_INSERT, "{INSERT}"),
    (wx.WXK_NUMPAD_DELETE, ""),
    (wx.WXK_NUMPAD_EQUAL, ""),
    (wx.WXK_NUMPAD_MULTIPLY, "{MULTIPLY}"),
    (wx.WXK_NUMPAD_ADD, "{ADD}"),
    (wx.WXK_NUMPAD_SEPARATOR, ""),
    (wx.WXK_NUMPAD_SUBTRACT, "{SUBTRACT}"),
    (wx.WXK_NUMPAD_DECIMAL, ""),
    (wx.WXK_NUMPAD_DIVIDE, "{DIVIDE}"),
    (wx.WXK_WINDOWS_LEFT, "{LWIN}"),
    (wx.WXK_WINDOWS_RIGHT, "{RWIN}"),
    (wx.WXK_WINDOWS_MENU, "{LWIN}"),
    (wx.WXK_COMMAND, ""),
    )


def GetSendkeys(code):
    """Returns a character for a key code.

    :param code: The character code.
    :type code: Integer."""
    if code >= 65 and code <= 122:
        return chr(code)
    else:
        t = (v for i, (k, v) in enumerate(SENDKEYS_TABLE_VIRTUAL) if k == code)
        return next(t, None)

# START SENDINPUT TYPE DECLARATIONS
PUL = POINTER(c_ulong)


class KeyBdInput(Structure):
    _fields_ = [("wVk", c_ushort),
             ("wScan", c_ushort),
             ("dwFlags", c_ulong),
             ("time", c_ulong),
             ("dwExtraInfo", PUL)]


class HardwareInput(Structure):
    _fields_ = [("uMsg", c_ulong),
             ("wParamL", c_short),
             ("wParamH", c_ushort)]


class MouseInput(Structure):
    _fields_ = [("dx", c_long),
             ("dy", c_long),
             ("mouseData", c_ulong),
             ("dwFlags", c_ulong),
             ("time", c_ulong),
             ("dwExtraInfo", PUL)]


class Input_I(Union):
    _fields_ = [("ki", KeyBdInput),
              ("mi", MouseInput),
              ("hi", HardwareInput)]


class Input(Structure):
    _fields_ = [("type", c_ulong),
             ("ii", Input_I)]


class POINT(Structure):
    _fields_ = [("x", c_ulong),
             ("y", c_ulong)]


# END SENDINPUT TYPE DECLARATIONS

#  LEFTDOWN   = 0x00000002,
#  LEFTUP     = 0x00000004,
#  MIDDLEDOWN = 0x00000020,
#  MIDDLEUP   = 0x00000040,
#  MOVE       = 0x00000001,
#  ABSOLUTE   = 0x00008000,
#  RIGHTDOWN  = 0x00000008,
#  RIGHTUP    = 0x00000010

MIDDLEDOWN = 0x00000020
MIDDLEUP = 0x00000040
MOVE = 0x00000001
ABSOLUTE = 0x00008000
RIGHTDOWN = 0x00000008
RIGHTUP = 0x00000010


FInputs = Input * 2
extra = c_ulong(0)

click = Input_I()
click.mi = MouseInput(0, 0, 0, 2, 0, pointer(extra))
release = Input_I()
release.mi = MouseInput(0, 0, 0, 4, 0, pointer(extra))

x = FInputs((0, click), (0, release))
#user32.SendInput(2, pointer(x), sizeof(x[0])) CLICK & RELEASE

x2 = FInputs((0, click))
#user32.SendInput(2, pointer(x2), sizeof(x2[0])) CLICK & HOLD

x3 = FInputs((0, release))
#user32.SendInput(2, pointer(x3), sizeof(x3[0])) RELEASE HOLD


def send_input(type_, data, flags, scan=0, mouseData=0):
    Inputs = Input * 1
    kinput = None
    if type_ == 'm':
        m = Input_I()
        m.mi = MouseInput(data[0], data[1], mouseData, flags, 0,
                          pointer(extra))
        kinput = Inputs((0, m))
    elif type_ == 'k':
        k = Input_I()
        k.ki = KeyBdInput(data, 0, flags, scan, pointer(extra))
        kinput = Inputs((1, k))
    if kinput is not None:
        windll.user32.SendInput(1, pointer(kinput), sizeof(kinput[0]))


def key(event, kcode):
    windll.user32.keybd_event(kcode, 0, 0 if event == 257 else 2, 0)


def move(x, y):
    windll.user32.SetCursorPos(x, y)


def getpos():
    global pt
    pt = POINT()
    windll.user32.GetCursorPos(byref(pt))
    return (pt.x, pt.y)


def move_to(x, y):
    (curx, cury) = getpos()
    return move(curx + x, cury + y)


def slide(a, b, speed=0):
    while True:
        if speed == 'slow':
            time.sleep(0.005)
            Tspeed = 2
        if speed == 'fast':
            time.sleep(0.001)
            Tspeed = 5
        if speed == 0:
            time.sleep(0.001)
            Tspeed = 3
        x = getpos()[0]
        y = getpos()[1]
        if abs(x - a) < 5:
            if abs(y - b) < 5:
                break

        if a < x:
            x -= Tspeed
        if a > x:
            x += Tspeed
        if b < y:
            y -= Tspeed
        if b > y:
            y += Tspeed
        move(x, y)


def slide_to(x, y):
    (curx, cury) = getpos()
    return slide(curx + x, cury + y)


def click():
    windll.user32.SendInput(2, pointer(x), sizeof(x[0]))


def hold():
    windll.user32.SendInput(2, pointer(x2), sizeof(x2[0]))


def release():
    windll.user32.SendInput(2, pointer(x3), sizeof(x3[0]))


def rightclick():
    windll.user32.mouse_event(RIGHTDOWN, 0, 0, 0, 0)
    windll.user32.mouse_event(RIGHTUP, 0, 0, 0, 0)


def righthold():
    windll.user32.mouse_event(RIGHTDOWN, 0, 0, 0, 0)


def rightrelease():
    windll.user32.mouse_event(RIGHTUP, 0, 0, 0, 0)


def middleclick():
    windll.user32.mouse_event(MIDDLEDOWN, 0, 0, 0, 0)
    windll.user32.mouse_event(MIDDLEUP, 0, 0, 0, 0)


def middledown():
    windll.user32.mouse_event(MIDDLEDOWN, 0, 0, 0, 0)


def middleup():
    windll.user32.mouse_event(MIDDLEUP, 0, 0, 0, 0)
