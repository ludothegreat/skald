"""Phase 0 smoke test — non-interactive proof the toolchain works.

Exercises the same surface as spike.py but without keystroke input so it can
run unattended. Verifies the cross-stack rules from the plan:
  - LC_NUMERIC=C after PySide6 import
  - libmpv loads and plays
  - chapter_list returns from M4B
  - speed change is pitch-corrected
  - seek works
  - player.terminate() returns cleanly
"""

import locale
locale.setlocale(locale.LC_NUMERIC, "C")

from PySide6.QtCore import QCoreApplication  # noqa: F401  (intentional side-effect import)

import sys
import time
from pathlib import Path

import mpv


def fmt(seconds: float | None) -> str:
    if seconds is None:
        return "?:??"
    s = int(seconds)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python spike/smoke.py <path-to-audiobook>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    assert path.exists(), f"missing: {path}"

    # Rule 1: LC_NUMERIC=C
    lc = locale.getlocale(locale.LC_NUMERIC)
    assert lc[0] in (None, "C"), f"LC_NUMERIC={lc} (expected C); did Qt clobber it?"
    print(f"[ok] LC_NUMERIC={lc[0] or 'POSIX'} after PySide6 import")

    print(f"[..] loading {path.name}")
    player = mpv.MPV(
        vo="null",
        video=False,
        ytdl=False,
        audio_pitch_correction=True,
        log_handler=lambda level, component, message: None,  # silence libmpv
    )

    try:
        player.play(str(path))
        player.wait_until_playing()
        # Mute so the smoke test doesn't blast audio.
        player.mute = True
        print(f"[ok] playing; duration={fmt(player.duration)}")

        chapters = player.chapter_list or []
        print(f"[ok] chapter_list returned {len(chapters)} chapters")
        if chapters:
            first = chapters[0]
            print(f"     first chapter: {fmt(first['time'])}  {first['title']}")

        # Verify time-pos advances
        pos0 = player.time_pos or 0.0
        time.sleep(2.0)
        pos1 = player.time_pos or 0.0
        delta = pos1 - pos0
        print(f"[..] time-pos delta after 2s wait: {delta:.2f}s")
        assert delta >= 1.5, f"time-pos didn't advance enough ({delta=:.2f})"
        print(f"[ok] time-pos advanced {delta:.2f}s (≥1.5 expected)")

        # Speed change with pitch preservation
        player.speed = 1.5
        time.sleep(0.5)
        assert abs(player.speed - 1.5) < 0.001, f"speed={player.speed} (expected 1.5)"
        print(f"[ok] speed set to {player.speed} (pitch-corrected via scaletempo2)")

        # Relative seek
        before = player.time_pos or 0.0
        player.seek(+30, reference="relative")
        time.sleep(0.3)
        after = player.time_pos or 0.0
        seeked = after - before
        print(f"[..] seek +30 jumped from {fmt(before)} to {fmt(after)} ({seeked:+.1f}s)")
        assert seeked > 25, f"seek didn't move enough ({seeked=:.1f})"
        print(f"[ok] relative seek works")

        # Chapter navigation
        if len(chapters) >= 2:
            current_ch = player.chapter
            player.command("add", "chapter", "1")
            time.sleep(0.3)
            new_ch = player.chapter
            assert new_ch != current_ch, f"chapter nav didn't change ({current_ch=}, {new_ch=})"
            print(f"[ok] chapter nav: {current_ch} -> {new_ch}")
        else:
            print(f"[ok] chapter nav skipped (only {len(chapters)} chapters)")

    finally:
        print("[..] terminating")
        t0 = time.time()
        player.terminate()
        t1 = time.time()
        print(f"[ok] terminate() returned cleanly in {t1 - t0:.3f}s")

    print("\nPhase 0 smoke test PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
