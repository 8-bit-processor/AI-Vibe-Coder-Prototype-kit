"""
Notification sounds for Local Vibe Coder.

Uses Windows built-in winsound (no extra dependencies) with a fallback
terminal bell for other platforms. Sounds can be toggled on/off at runtime.
"""

import sys
import threading


# Global mute flag - toggled via /sound command in the CLI
_muted = False


def mute():
    global _muted
    _muted = True


def unmute():
    global _muted
    _muted = False


def toggle() -> bool:
    """Toggle mute state. Returns True if now enabled, False if muted."""
    global _muted
    _muted = not _muted
    return not _muted


def is_enabled() -> bool:
    return not _muted


def _play_async(fn, *args, **kwargs):
    """Run a sound function in a daemon thread so it never blocks the UI."""
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()


if sys.platform == "win32":
    import winsound

    # Windows System Sound aliases
    _SOUNDS = {
        "done":    winsound.MB_ICONASTERISK,   # "Asterisk" - soft chime
        "error":   winsound.MB_ICONHAND,       # "Critical Stop"
        "tool":    winsound.MB_OK,             # subtle click
    }

    def _beep_windows(sound_type: str):
        if _muted:
            return
        flag = _SOUNDS.get(sound_type, winsound.MB_OK)
        try:
            winsound.MessageBeep(flag)
        except Exception:
            pass

    def play_done():
        """Two-tone ascending chime: task completed."""
        if _muted:
            return
        def _play():
            try:
                winsound.Beep(880, 120)   # A5
                winsound.Beep(1046, 180)  # C6
            except Exception:
                pass
        _play_async(_play)

    def play_error():
        """Low descending tone: something went wrong."""
        if _muted:
            return
        def _play():
            try:
                winsound.Beep(440, 120)  # A4
                winsound.Beep(330, 220)  # E4
            except Exception:
                pass
        _play_async(_play)

    def play_tool_call():
        """Subtle tick: a tool is being invoked."""
        if _muted:
            return
        def _play():
            try:
                winsound.Beep(600, 60)
            except Exception:
                pass
        _play_async(_play)

else:
    # Cross-platform terminal bell fallback

    def _bell():
        if not _muted:
            print("\a", end="", flush=True)

    def play_done():
        _play_async(_bell)

    def play_error():
        _play_async(_bell)
        _play_async(_bell)

    def play_tool_call():
        pass  # Too noisy on non-Windows for every tool call
