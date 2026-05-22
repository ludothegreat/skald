"""Phase 0 spike — prove the toolchain works on Linux.

Plays an audiobook via python-mpv with chapter detection and keystroke transport.
Disposable after Phase 1; the working bits get recycled into src/skald/player.py.

Usage:
    python spike/spike.py <path-to-audiobook>
"""

# Locale fix BEFORE anything else — Qt clobbers LC_NUMERIC on import and
# libmpv parses numeric properties using the C locale.
import locale
locale.setlocale(locale.LC_NUMERIC, "C")

# Import PySide6 specifically to prove the locale fix survives Qt's import.
# In the real app this happens via skald/__main__.py.
from PySide6.QtCore import QCoreApplication  # noqa: F401  (intentional side-effect)

import sys
import threading
from pathlib import Path

import mpv
import readchar


def fmt(seconds: float | None) -> str:
    if seconds is None:
        return "?:??"
    s = int(seconds)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def print_status(player: mpv.MPV) -> None:
    pos = player.time_pos
    dur = player.duration
    speed = player.speed
    chapter_idx = player.chapter
    chapters = player.chapter_list or []
    chap_title = chapters[chapter_idx]["title"] if (chapter_idx is not None and 0 <= chapter_idx < len(chapters)) else "—"
    paused = " ⏸" if player.pause else ""
    print(
        f"\r[{fmt(pos)} / {fmt(dur)}] {speed:.2f}x ch{chapter_idx}: {chap_title[:50]}{paused}   ",
        end="",
        flush=True,
    )


def status_loop(player: mpv.MPV, stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            print_status(player)
        except Exception as e:  # noqa: BLE001
            print(f"\n[status loop] {e}", flush=True)
        stop.wait(1.0)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 2

    # Verify locale fix is active.
    lc = locale.getlocale(locale.LC_NUMERIC)
    assert lc[0] in (None, "C"), f"LC_NUMERIC is {lc}, expected C"

    print(f"Loading: {path.name}", flush=True)
    player = mpv.MPV(
        vo="null",
        video=False,
        ytdl=False,
        audio_pitch_correction=True,
        log_handler=lambda level, component, message: None,  # silence libmpv chatter
    )

    try:
        player.play(str(path))
        # Wait for libmpv to actually start playing so chapter_list is populated.
        player.wait_until_playing()

        chapters = player.chapter_list or []
        print(f"\nChapters: {len(chapters)}", flush=True)
        for i, c in enumerate(chapters[:8]):
            print(f"  {i:3d}  {fmt(c['time'])}  {c['title']}", flush=True)
        if len(chapters) > 8:
            print(f"  ... ({len(chapters) - 8} more)", flush=True)

        print(
            "\nControls: SPACE=play/pause  ←/→=seek 10s  ,/.=prev/next chapter  "
            "+/-=speed  q=quit\n",
            flush=True,
        )

        stop = threading.Event()
        t = threading.Thread(target=status_loop, args=(player, stop), daemon=True)
        t.start()

        while True:
            key = readchar.readkey()
            # readchar returns escape sequences for arrows
            if key in (readchar.key.SPACE, "p"):
                player.pause = not player.pause
            elif key == readchar.key.LEFT:
                player.seek(-10, reference="relative")
            elif key == readchar.key.RIGHT:
                player.seek(10, reference="relative")
            elif key == ",":
                player.command("add", "chapter", "-1")
            elif key == ".":
                player.command("add", "chapter", "1")
            elif key == "+":
                player.speed = min(player.speed + 0.1, 3.0)
            elif key == "-":
                player.speed = max(player.speed - 0.1, 0.5)
            elif key in ("q", readchar.key.ESC, readchar.key.CTRL_C):
                break
            print_status(player)
    finally:
        print("\nShutting down...", flush=True)
        try:
            stop.set()  # type: ignore[possibly-unbound]
        except NameError:
            pass
        player.terminate()
        print("Done.", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
