import json
import random
import re
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any, Protocol

import sdsp

RECORD = Path(__file__).resolve().parent / "hardware.json"


class Store(Protocol):
    def read8(self, address: int) -> int: ...

    def write8(self, address: int, value: int) -> None: ...


class Part(Protocol):
    model: str
    memory: Store
    registers: bytearray
    voices: list[sdsp.Voice]
    phase: int
    rendered: list[int]
    gaussian: tuple[int, ...]

    def read(self, address: int) -> int: ...

    def write(self, address: int, value: int) -> None: ...

    def reset(self) -> "Part": ...

    def clock(self) -> None: ...

    def run(self, clocks: int) -> None: ...

    def render(self, samples: int) -> list[int]: ...


SOURCE = 0x1000
SOURCE_BLOCKS = 128
QUIET = 0x2000
STEADY = 0x2100
SHORT = 0x2200
DIRECTORY = 0x02
ECHO = 0x40
ECHO_SPAN = 0x800
UNTOUCHED = 0xAA
LOUD = 0x7F
UNITY_PITCH = 0x10
SETTLE = 16
SIDES = {"Left": 0, "Right": 1, "L": 0, "R": 1}
NUMBERS = {SOURCE: 0, QUIET: 1, STEADY: 2, SHORT: 3}
BRR_BLOCK_BYTES = 9
FIR = 0x0F
NEWEST_TAP = FIR + 0x70
VOLL = 0x00
PITCHH = 0x03
SRCN = 0x04
GAIN = 0x07
MVOLL = 0x0C
MVOLR = 0x1C
KON = 0x4C
DIR = 0x5D
FLG = 0x6C
ECHO_WRITES_OFF = 0x20


@cache
def record() -> dict[str, Any]:
    held: dict[str, Any] = json.loads(RECORD.read_text())
    return held


def register_map() -> dict[str, Any]:
    held: dict[str, Any] = record()["registerMap"]
    return held


def at(key: str, name: str) -> int:
    return next(
        int(row.get("offset", row.get("address")), 16)
        for row in register_map()[key]
        if row["register"] == name
    )


def quoted(key: str, name: str) -> str:
    return str(next(row["functionQuote"] for row in register_map()[key] if row["register"] == name))


def numbers_in(text: str) -> list[int]:
    return [int(found) for found in re.findall(r"\d+", text)]


def side_of(text: str) -> int:
    return SIDES[re.findall(r"\b(Left|Right|L|R)\b", text)[0]]


def a_sample(memory: sdsp.Memory, start: int, data: Callable[[], int], blocks: int = 2) -> None:
    for block in range(blocks):
        base = start + block * BRR_BLOCK_BYTES
        memory.write8(base, 0xC3 if block == blocks - 1 else 0xC0)
        for offset in range(1, BRR_BLOCK_BYTES):
            memory.write8(base + offset, data())


def contents(memory: sdsp.Memory, start: int = 0, length: int = 0x10000) -> bytes:
    return bytes(memory.read8(address) for address in range(start, start + length))


def an_entry(memory: sdsp.Memory, page: int, number: int, start: int) -> None:
    for index, value in enumerate(start.to_bytes(2, "little") * 2):
        memory.write8(page * 0x100 + number * 4 + index, value)


def a_memory(fill: int = 0) -> sdsp.Memory:
    memory = sdsp.Memory(fill=fill)
    rng = random.Random(7)
    a_sample(memory, SOURCE, lambda: rng.randrange(256), SOURCE_BLOCKS)
    a_sample(memory, QUIET, lambda: 0)
    a_sample(memory, STEADY, lambda: 0x77)
    a_sample(memory, SHORT, lambda: rng.randrange(256))
    for start, number in NUMBERS.items():
        an_entry(memory, DIRECTORY, number, start)
    return memory


def a_part(memory: sdsp.Memory | None = None) -> Part:
    chip = sdsp.Chip("s-dsp", a_memory() if memory is None else memory).reset()
    chip.write(DIR, DIRECTORY)
    chip.write(MVOLL, LOUD)
    chip.write(MVOLR, LOUD)
    chip.write(FLG, ECHO_WRITES_OFF)
    return chip


def voiced(chip: Part, voices: int, source: int = SOURCE, gain: int = LOUD) -> Part:
    for voice in chip.voices:
        if voices & voice.bit:
            chip.write(voice.base + VOLL, LOUD)
            chip.write(voice.base + VOLL + 1, LOUD)
            chip.write(voice.base + PITCHH, UNITY_PITCH)
            chip.write(voice.base + SRCN, NUMBERS[source])
            chip.write(voice.base + GAIN, gain)
    return chip


def keyed(chip: Part, voices: int = 0x01, source: int = SOURCE, gain: int = LOUD) -> Part:
    voiced(chip, voices, source, gain).write(KON, voices)
    return chip


def consumed(voice: sdsp.Voice) -> int:
    blocks = (voice.brr_address - SOURCE) // BRR_BLOCK_BYTES
    return blocks * 16 + (voice.brr_offset - 1) * 2


def silent(samples: list[int]) -> bool:
    return set(samples) == {0}


def each_sample(chip: Part, samples: int, look: Callable[[], int]) -> list[int]:
    found = []
    for _ in range(samples):
        chip.render(1)
        found.append(look())
    return found


def moved(chip: Part, clocks: int) -> set[int]:
    found: set[int] = set()
    for _ in range(clocks):
        before = bytes(chip.registers)
        chip.clock()
        found |= {
            at for at, (a, b) in enumerate(zip(before, chip.registers, strict=True)) if a != b
        }
    return found


def own_side_and_other(rendered: list[int], quote: str) -> list[bool]:
    side = side_of(quote)
    return [silent(rendered[side::2]), silent(rendered[1 - side :: 2])]


def a_volume_silences(address: int, quote: str) -> list[bool]:
    chip = keyed(a_part())
    chip.write(address, 0)
    return own_side_and_other(chip.render(64), quote)
