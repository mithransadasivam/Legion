"""Non-blocking Enter detection, so the user can cut in while Legion is talking.

A terminal holds on to keys pressed while a program isn't reading, and hands them
to the next prompt. Left alone, one stray Enter during a reply shifts every
later press out of step: "start talking" stops the recording, and "stop" starts it.
"""

import sys

if sys.platform == "win32":
    import msvcrt

    def enter_pressed() -> bool:
        pressed = False
        while msvcrt.kbhit():
            pressed |= msvcrt.getwch() in "\r\n"
        return pressed

    def discard_pending_keys() -> None:
        while msvcrt.kbhit():
            msvcrt.getwch()

else:
    import select
    import termios

    def enter_pressed() -> bool:
        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if not ready:
            return False
        if not sys.stdin.readline():
            raise EOFError
        return True

    def discard_pending_keys() -> None:
        if sys.stdin.isatty():
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
