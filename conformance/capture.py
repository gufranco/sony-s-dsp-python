"""Read the DSP configuration out of music dumps you already have.

An SPC dump is a snapshot of a running audio unit: a small header, sixty four
kilobytes of audio RAM, and the hundred and twenty eight DSP registers. Those two
halves are very different things and only one of them can travel.

**The RAM never leaves.** It holds the BRR samples and the sequence data, which
together are the music. This tool reads past it and never writes a byte of it
anywhere.

**The registers are configuration.** Volumes, pitches, envelope rates, which
voices feed the echo, where the sample directory sits, the eight filter taps.
They are the parameters a driver poked into a peripheral, they describe how the
chip was being driven rather than what was being played, and without the samples
they reproduce nothing. That is the half worth having, because a real driver
configures the DSP in ways no random generator would think of: envelope rates
clustered where instruments actually sit, echo delays a composer chose, filter
taps that are mostly zero except when they are not.

So the corpus generated from this pairs **real register states** with **synthetic
sample data**, and takes its expected audio from the reference chip. What ships
is how the hardware was driven, never what came out of it.
"""

import collections
import json
import sys
from pathlib import Path
from typing import Any

MAGIC = b"SNES-SPC700 Sound File Data"

RAM_AT = 0x100
RAM_BYTES = 0x10000
REGISTERS_AT = RAM_AT + RAM_BYTES
REGISTER_COUNT = 128

VOICE_COUNT = 8
V_ADSR0 = 0x05
REG_PMON = 0x2D
REG_NON = 0x3D
REG_EON = 0x4D
REG_DIR = 0x5D
REG_FLG = 0x6C
REG_EDL = 0x7D


def registers(path: Path | str) -> list[int] | None:
    """The DSP registers in one dump, or nothing if the file is not one.

    Only the register block is read back. The audio RAM in between is skipped
    rather than loaded, so the music never enters this process at all.
    """
    path = Path(path)
    try:
        with path.open("rb") as handle:
            if handle.read(len(MAGIC)) != MAGIC:
                return None
            handle.seek(REGISTERS_AT)
            found = handle.read(REGISTER_COUNT)
    except OSError:
        return None
    if len(found) != REGISTER_COUNT:
        return None
    return list(found)


def dumps(root: Path | str, limit: int | None = None) -> list[Path]:
    """Every dump under a directory, in a fixed order, up to a limit."""
    found = sorted(Path(root).rglob("*.spc"))
    return found[:limit] if limit else found


def census(states: list[list[int]]) -> dict[str, Any]:
    """What the drivers were doing, with none of what they were playing."""
    directories: collections.Counter[int] = collections.Counter()
    flags: collections.Counter[int] = collections.Counter()
    delays: collections.Counter[int] = collections.Counter()
    adsr = 0
    modulation = noise = echo = 0

    for state in states:
        directories[state[REG_DIR]] += 1
        flags[state[REG_FLG]] += 1
        delays[state[REG_EDL] & 0x0F] += 1
        adsr += sum(1 for voice in range(VOICE_COUNT) if state[voice * 0x10 + V_ADSR0] & 0x80)
        modulation += 1 if state[REG_PMON] else 0
        noise += 1 if state[REG_NON] else 0
        echo += 1 if state[REG_EON] else 0

    return {
        "comment": (
            "A census of how real drivers configured the DSP: sample directory pages, "
            "flag registers, echo delays, and how many voices used the envelope. The "
            "audio RAM of every dump was skipped rather than read."
        ),
        "states": len(states),
        "directories": {str(page): count for page, count in sorted(directories.items())},
        "flags": {str(value): count for value, count in sorted(flags.items())},
        "echo_delays": {str(value): count for value, count in sorted(delays.items())},
        "adsr_voices": adsr,
        "pitch_modulation": modulation,
        "noise": noise,
        "echo_send": echo,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: capture.py <dump directory> <census out> [limit]")
        return 2

    root = Path(argv[0])
    if not root.is_dir():
        print(f"  nothing at {root}")
        return 2

    limit = int(argv[2]) if len(argv) > 2 else None
    states = [found for found in (registers(path) for path in dumps(root, limit)) if found]

    if not states:
        print(f"  no dumps under {root}")
        return 1

    found = census(states)
    Path(argv[1]).write_text(json.dumps(found, indent=2) + "\n")

    print(f"  {found['states']} register states from {root}")
    print(
        f"  {len(found['directories'])} sample directory pages, {found['adsr_voices']} voices on envelopes"
    )
    print(f"  written to {argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
