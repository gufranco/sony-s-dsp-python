import json
import random
import re
import sys
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sdsp import core
from sdsp.memory import Memory

HERE = Path(__file__).resolve().parent
FACTS: dict[str, Any] = json.loads((HERE / "hardware.json").read_text())
MAP: dict[str, Any] = FACTS["registerMap"]

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
NEWEST_TAP = core.REG_FIR + 0x70


def at(key: str, name: str) -> int:
    return next(
        int(row.get("offset", row.get("address")), 16)
        for row in MAP[key]
        if row["register"] == name
    )


def quoted(key: str, name: str) -> str:
    return str(next(row["functionQuote"] for row in MAP[key] if row["register"] == name))


def numbers_in(text: str) -> list[int]:
    return [int(found) for found in re.findall(r"\d+", text)]


def side_of(text: str) -> int:
    return SIDES[re.findall(r"\b(Left|Right|L|R)\b", text)[0]]


def a_sample(memory: Memory, start: int, data: Callable[[], int], blocks: int = 2) -> None:
    for block in range(blocks):
        base = start + block * core.BRR_BLOCK_BYTES
        memory.write8(base, 0xC3 if block == blocks - 1 else 0xC0)
        for offset in range(1, core.BRR_BLOCK_BYTES):
            memory.write8(base + offset, data())


def an_entry(memory: Memory, page: int, number: int, start: int) -> None:
    for index, value in enumerate(start.to_bytes(2, "little") * 2):
        memory.write8(page * 0x100 + number * 4 + index, value)


def a_memory(fill: int = 0) -> Memory:
    memory = Memory(fill=fill)
    rng = random.Random(7)
    a_sample(memory, SOURCE, lambda: rng.randrange(256), SOURCE_BLOCKS)
    a_sample(memory, QUIET, lambda: 0)
    a_sample(memory, STEADY, lambda: 0x77)
    a_sample(memory, SHORT, lambda: rng.randrange(256))
    for start, number in NUMBERS.items():
        an_entry(memory, DIRECTORY, number, start)
    return memory


def a_part(memory: Memory | None = None) -> core.Chip:
    chip = core.Chip(a_memory() if memory is None else memory).reset()
    chip.write(core.REG_DIR, DIRECTORY)
    chip.write(core.REG_MVOLL, LOUD)
    chip.write(core.REG_MVOLL + 0x10, LOUD)
    chip.write(core.REG_FLG, core.FLG_ECHO_OFF)
    return chip


def voiced(chip: core.Chip, voices: int, source: int = SOURCE, gain: int = LOUD) -> core.Chip:
    for voice in chip.voices:
        if voices & voice.bit:
            chip.write(voice.base + core.V_VOLL, LOUD)
            chip.write(voice.base + core.V_VOLL + 1, LOUD)
            chip.write(voice.base + core.V_PITCHH, UNITY_PITCH)
            chip.write(voice.base + core.V_SRCN, NUMBERS[source])
            chip.write(voice.base + core.V_GAIN, gain)
    return chip


def keyed(chip: core.Chip, voices: int = 0x01, source: int = SOURCE, gain: int = LOUD) -> core.Chip:
    voiced(chip, voices, source, gain).write(core.REG_KON, voices)
    return chip


def consumed(voice: core.Voice) -> int:
    blocks = (voice.brr_address - SOURCE) // core.BRR_BLOCK_BYTES
    return blocks * 16 + (voice.brr_offset - 1) * 2


def silent(samples: list[int]) -> bool:
    return set(samples) == {0}


def each_sample(chip: core.Chip, samples: int, look: Callable[[], int]) -> list[int]:
    found = []
    for _ in range(samples):
        chip.render(1)
        found.append(look())
    return found


def moved(chip: core.Chip, clocks: int) -> set[int]:
    found: set[int] = set()
    for _ in range(clocks):
        before = bytes(chip.registers)
        chip.clock()
        found |= {
            at for at, (a, b) in enumerate(zip(before, chip.registers, strict=True)) if a != b
        }
    return found


def echoing(fill: int = 0x24) -> tuple[core.Chip, Memory]:
    memory = Memory(fill=fill)
    chip = core.Chip(memory).reset()
    chip.write(core.REG_FLG, core.FLG_ECHO_OFF)
    chip.write(core.REG_EVOLL, LOUD)
    chip.write(core.REG_EVOLL + 0x10, LOUD)
    chip.write(core.REG_ESA, ECHO)
    chip.write(core.REG_EDL, 1)
    return chip, memory


def own_side_and_other(rendered: list[int], quote: str) -> list[bool]:
    side = side_of(quote)
    return [silent(rendered[side::2]), silent(rendered[1 - side :: 2])]


def a_volume_silences(address: int, quote: str) -> list[bool]:
    chip = keyed(a_part())
    chip.write(address, 0)
    return own_side_and_other(chip.render(64), quote)


def an_echo_volume_silences(address: int, quote: str) -> list[bool]:
    chip, _ = echoing()
    chip.write(NEWEST_TAP, LOUD)
    chip.write(address, 0)
    return own_side_and_other(chip.render(SETTLE), quote)


def progress(low: int, high: int, pitch: int) -> int:
    chip = keyed(a_part())
    chip.write(low, pitch & 0xFF)
    chip.write(high, pitch >> 8 & 0xFF)
    chip.render(256)
    return consumed(chip.voices[0])


def enveloped(first: int, second: int, adsr: tuple[int, int]) -> int:
    chip = voiced(a_part(), 0x01)
    chip.write(first, adsr[0])
    chip.write(second, adsr[1])
    chip.write(core.REG_KON, 0x01)
    chip.render(200)
    return chip.voices[0].envelope


def designated(gain: int, envx: int, value: int) -> int:
    chip = keyed(a_part())
    chip.write(gain, value)
    chip.render(SETTLE)
    return chip.read(envx)


def output_trace(outx: int, volume: int, gain: int) -> list[int]:
    chip = keyed(a_part(), gain=gain)
    chip.write(core.V_VOLL, volume)
    chip.write(core.V_VOLL + 1, volume)
    return each_sample(chip, 64, lambda: chip.read(outx))


def keyed_by(address: int, value: int) -> list[int]:
    chip = voiced(a_part(), 0xFF)
    chip.write(address, value)
    chip.render(4)
    return [voice.index for voice in chip.voices if voice.envelope_mode == core.ENV_ATTACK]


def flag_effects(address: int, flags: int) -> tuple[bool, bool, bool, bool]:
    memory = a_memory(fill=UNTOUCHED)
    chip = keyed(a_part(memory))
    chip.write(core.REG_ESA, ECHO)
    chip.write(core.REG_EDL, 1)
    chip.render(SETTLE)
    chip.write(address, flags)
    rendered = chip.render(64)
    echoed = memory.data[ECHO * 0x100 : ECHO * 0x100 + ECHO_SPAN]
    return (
        chip.voices[0].envelope_mode == core.ENV_RELEASE,
        silent(rendered[-32:]),
        echoed != bytes([UNTOUCHED]) * ECHO_SPAN,
        chip.noise != 0x4000,
    )


def fed_back(address: int, value: int) -> bytes:
    chip, memory = echoing()
    chip.write(NEWEST_TAP, LOUD)
    chip.write(core.REG_FLG, 0)
    chip.write(address, value)
    chip.render(4)
    return bytes(memory.data[ECHO * 0x100 + 4 : ECHO * 0x100 + 16])


def everything_after(address: int, value: int) -> tuple[list[int], bytes, bytes]:
    memory = a_memory()
    chip = keyed(a_part(memory))
    chip.write(core.REG_ESA, ECHO)
    chip.write(core.REG_EON, 0x01)
    chip.write(core.REG_EVOLL, LOUD)
    chip.write(NEWEST_TAP, LOUD)
    chip.write(core.REG_FLG, 0)
    chip.write(address, value)
    rendered = chip.render(64)
    others = chip.registers[:address] + chip.registers[address + 1 :]
    return rendered, bytes(memory.data), bytes(others)


def modulated(address: int, pmon: int, modulator_gain: int) -> int:
    chip = voiced(a_part(), 0x01, STEADY, modulator_gain)
    keyed(chip, 0x02)
    chip.write(core.REG_KON, 0x03)
    chip.write(address, pmon)
    chip.render(256)
    return consumed(chip.voices[1])


def noisy(address: int, value: int) -> list[int]:
    chip = keyed(a_part(), 0xFF, QUIET)
    chip.write(address, value)
    chip.render(SETTLE)
    return [voice.index for voice in chip.voices if chip.read(voice.base + core.V_OUTX)]


def echo_reached(address: int, value: int) -> bool:
    memory = a_memory()
    chip = keyed(a_part(memory))
    chip.write(core.REG_ESA, ECHO)
    chip.write(core.REG_EDL, 1)
    chip.write(core.REG_FLG, 0)
    chip.write(address, value)
    chip.render(64)
    return any(memory.data[ECHO * 0x100 : ECHO * 0x100 + ECHO_SPAN])


def played_from(address: int, page: int) -> int:
    memory = a_memory()
    an_entry(memory, 0x30, 0, QUIET)
    an_entry(memory, 0x31, 0, SHORT)
    chip = keyed(a_part(memory))
    chip.write(address, page)
    chip.render(SETTLE)
    return chip.voices[0].brr_address & ~0xFF


def echo_lands(address: int, page: int) -> int:
    chip, memory = echoing(UNTOUCHED)
    chip.write(core.REG_FLG, 0)
    chip.write(address, page)
    chip.render(4)
    return max(at for at, value in enumerate(memory.data) if value != UNTOUCHED) >> 8


def echo_written(address: int, value: int) -> int:
    chip, memory = echoing(UNTOUCHED)
    chip.write(core.REG_FLG, 0)
    chip.write(address, value)
    chip.render(600)
    return sum(1 for byte in memory.data if byte != UNTOUCHED)


def filtered(address: int) -> tuple[int, int]:
    chip, _ = echoing()
    chip.write(address, 0x40)
    rendered = chip.render(SETTLE)
    return rendered[-2], rendered[-1]


class VoiceRegisterTest(unittest.TestCase):
    def test_the_left_volume_reaches_its_own_channel_alone(self) -> None:
        # Arrange
        address, quote = at("voice", "VOL (L)"), quoted("voice", "VOL (L)")

        # Act
        found = a_volume_silences(address, quote)

        # Assert
        self.assertEqual(found, [True, False])

    def test_the_right_volume_reaches_its_own_channel_alone(self) -> None:
        # Arrange
        address, quote = at("voice", "VOL (R)"), quoted("voice", "VOL (R)")

        # Act
        found = a_volume_silences(address, quote)

        # Assert
        self.assertEqual(found, [True, False])

    def test_the_pitch_is_the_printed_number_of_bits_across_both_registers(self) -> None:
        # Arrange
        low, high = at("voice", "P (L)"), at("voice", "P (H)")
        bits = numbers_in(quoted("voice", "P (L)"))[0]
        pitches = [0x0FFF, 0x0F00, 0x0FFF | 1 << bits, 0x0FFF | 1 << (bits - 1)]

        # Act
        found = [progress(low, high, pitch) for pitch in pitches]

        # Assert
        self.assertEqual(
            (found[1] == found[0], found[2] == found[0], found[3] == found[0]),
            (False, True, False),
        )

    def test_the_source_number_reaches_the_top_of_its_printed_range(self) -> None:
        # Arrange
        highest = numbers_in(quoted("voice", "SRCN"))[-1]
        memory = a_memory()
        an_entry(memory, DIRECTORY, highest, SHORT)
        chip = keyed(a_part(memory), source=QUIET)
        chip.write(at("voice", "SRCN"), highest)

        # Act
        chip.render(SETTLE)

        # Assert
        self.assertEqual(chip.voices[0].brr_address & ~0xFF, SHORT)

    def test_the_mode_bit_hands_the_envelope_to_adsr_or_to_gain(self) -> None:
        # Arrange
        select = FACTS["envelope"]["modeSelect"]
        first, second = at("voice", select["register"]), at("voice", "ADSR (2)")
        slowest_attack = 0x00

        # Act
        found = [
            enveloped(first, second, (slowest_attack | 1 << select["bit"], 0)),
            enveloped(first, second, (slowest_attack, 0)),
        ]

        # Assert
        self.assertEqual((found[0] == found[1], found[1] >> 4), (False, LOUD))

    def test_the_second_adsr_byte_counts_only_while_the_mode_bit_is_set(self) -> None:
        # Arrange
        select = FACTS["envelope"]["modeSelect"]
        first, second = at("voice", select["register"]), at("voice", "ADSR (2)")
        fast, mode = 0x7F, 1 << select["bit"]

        # Act
        found = [
            enveloped(first, second, adsr)
            for adsr in ((fast | mode, 0x00), (fast | mode, 0xE0), (fast, 0x00), (fast, 0xE0))
        ]

        # Assert
        self.assertEqual((found[0] == found[1], found[2] == found[3]), (False, True))

    def test_the_program_designates_the_envelope_freely(self) -> None:
        # Arrange
        gain, envx = at("voice", "GAIN"), at("voice", "ENVX")
        chosen = random.Random(11).sample(range(0x80), 6)

        # Act
        found = [designated(gain, envx, value) for value in chosen]

        # Assert
        self.assertEqual(found, chosen)

    def test_the_envelope_register_is_rewritten_every_sample(self) -> None:
        # Arrange
        envx = at("voice", "ENVX")
        chip = keyed(a_part())
        chip.render(SETTLE)
        chip.write(envx, 0)

        # Act
        chip.render(1)

        # Assert
        self.assertEqual(chip.read(envx), LOUD)

    def test_the_output_register_follows_the_envelope_and_ignores_the_volume(self) -> None:
        # Arrange
        outx = at("voice", "OUTX")

        # Act
        found = [output_trace(outx, 0, LOUD), output_trace(outx, LOUD, 0)]

        # Assert
        self.assertEqual([silent(trace) for trace in found], [False, True])

    def test_every_voice_answers_at_its_own_stride(self) -> None:
        # Arrange
        stride = MAP["voiceStride"]
        gain, envx = at("voice", "GAIN"), at("voice", "ENVX")
        values = [0x10 + 9 * voice for voice in range(stride["voices"])]
        chip = voiced(a_part(), 0xFF)
        for voice, value in enumerate(values):
            chip.write(voice * stride["stride"] + gain, value)
        chip.write(core.REG_KON, 0xFF)

        # Act
        chip.render(SETTLE)

        # Assert
        self.assertEqual(
            [chip.read(voice * stride["stride"] + envx) for voice in range(len(values))], values
        )

    def test_the_part_writes_exactly_the_registers_printed_as_its_own(self) -> None:
        # Arrange
        named = {row["register"]: at("voice", row["register"]) for row in MAP["voice"]}
        named |= {row["register"]: at("global", row["register"]) for row in MAP["global"]}
        printed = {named[name] for name in MAP["writtenByTheDsp"]["registers"]}
        chip = keyed(a_part(), source=SHORT)

        # Act
        found = moved(chip, 64 * 32)

        # Assert
        self.assertEqual(found, printed)


class GlobalRegisterTest(unittest.TestCase):
    def test_the_left_main_volume_reaches_its_own_channel_alone(self) -> None:
        # Arrange
        address, quote = at("global", "MVOL (L)"), quoted("global", "MVOL (L)")

        # Act
        found = a_volume_silences(address, quote)

        # Assert
        self.assertEqual(found, [True, False])

    def test_the_right_main_volume_reaches_its_own_channel_alone(self) -> None:
        # Arrange
        address, quote = at("global", "MVOL (R)"), quoted("global", "MVOL (R)")

        # Act
        found = a_volume_silences(address, quote)

        # Assert
        self.assertEqual(found, [True, False])

    def test_the_left_echo_volume_reaches_its_own_channel_alone(self) -> None:
        # Arrange
        address, quote = at("global", "EVOL (L)"), quoted("global", "EVOL (L)")

        # Act
        found = an_echo_volume_silences(address, quote)

        # Assert
        self.assertEqual(found, [True, False])

    def test_the_right_echo_volume_reaches_its_own_channel_alone(self) -> None:
        # Arrange
        address, quote = at("global", "EVOL (R)"), quoted("global", "EVOL (R)")

        # Act
        found = an_echo_volume_silences(address, quote)

        # Assert
        self.assertEqual(found, [True, False])

    def test_each_key_on_bit_keys_the_voice_printed_beside_it(self) -> None:
        # Arrange
        first_bit, last_bit, first_voice, _ = numbers_in(quoted("global", "KON"))
        address = at("global", "KON")

        # Act
        found = [keyed_by(address, 1 << bit) for bit in range(first_bit, last_bit + 1)]

        # Assert
        self.assertEqual(found, [[first_voice + n] for n in range(last_bit - first_bit + 1)])

    def test_key_off_releases_a_sounding_voice_to_nothing(self) -> None:
        # Arrange
        chip = keyed(a_part())
        chip.render(SETTLE)
        sounding = chip.voices[0].envelope
        chip.write(at("global", "KOF"), 0x01)

        # Act
        chip.render(300)

        # Assert
        self.assertEqual(
            (sounding > 0, chip.voices[0].envelope_mode, chip.voices[0].envelope),
            (True, core.ENV_RELEASE, 0),
        )

    def test_the_flag_register_switches_reset_mute_echo_and_noise_clock(self) -> None:
        # Arrange
        address = at("global", "FLG")
        flags = (0x80, 0x40, 0x20, 0x1F, 0x00)

        # Act
        found = [flag_effects(address, value) for value in flags]

        # Assert
        self.assertEqual(
            found,
            [
                (True, True, True, False),
                (False, True, True, False),
                (False, False, False, False),
                (False, False, True, True),
                (False, False, True, False),
            ],
        )

    def test_the_end_flag_rises_once_the_source_passes_its_end_block(self) -> None:
        # Arrange
        endx = at("global", "ENDX")
        chip = keyed(a_part(), source=SHORT)

        # Act
        found = each_sample(chip, 64, lambda: chip.read(endx) & 0x01)

        # Assert
        self.assertEqual((found[0], found[-1], found == sorted(found)), (0, 1, True))

    def test_echo_feedback_returns_the_echo_into_the_buffer(self) -> None:
        # Arrange
        address = at("global", "EFB")

        # Act
        found = [fed_back(address, value) for value in (0x00, 0x40)]

        # Assert
        self.assertEqual((found[0], found[1] == bytes(12)), (bytes(12), False))

    def test_the_register_printed_as_not_used_changes_nothing(self) -> None:
        # Arrange
        address = at("global", "---")

        # Act
        found = [everything_after(address, value) for value in (0x00, 0xFF)]

        # Assert
        self.assertEqual(found[0], found[1])

    def test_pitch_modulation_follows_the_output_of_the_voice_before(self) -> None:
        # Arrange
        address = at("global", "PMON")
        second_voice = 0x02

        # Act
        found = [
            modulated(address, 0x00, LOUD),
            modulated(address, second_voice, LOUD),
            modulated(address, second_voice, 0),
        ]

        # Assert
        self.assertEqual((found[1] == found[0], found[2] == found[0]), (False, True))

    def test_each_noise_bit_turns_noise_on_for_the_voice_printed_beside_it(self) -> None:
        # Arrange
        first_bit, last_bit, first_voice, _ = numbers_in(quoted("global", "NON"))
        address = at("global", "NON")

        # Act
        found = [noisy(address, 1 << bit) for bit in range(first_bit, last_bit + 1)]

        # Assert
        self.assertEqual(found, [[first_voice + n] for n in range(last_bit - first_bit + 1)])

    def test_echo_on_decides_whether_a_voice_reaches_the_echo_buffer(self) -> None:
        # Arrange
        address = at("global", "EON")

        # Act
        found = [echo_reached(address, value) for value in (0x00, 0x01)]

        # Assert
        self.assertEqual(found, [False, True])

    def test_the_directory_is_read_from_the_page_the_offset_names(self) -> None:
        # Arrange
        address = at("global", "DIR")

        # Act
        found = [played_from(address, page) for page in (0x30, 0x31)]

        # Assert
        self.assertEqual(found, [QUIET, SHORT])

    def test_the_echo_region_starts_at_the_page_the_offset_names(self) -> None:
        # Arrange
        address = at("global", "ESA")

        # Act
        found = [echo_lands(address, page) for page in (0x40, 0x50)]

        # Assert
        self.assertEqual(found, [0x40, 0x50])

    def test_only_the_printed_low_bits_of_the_echo_delay_count(self) -> None:
        # Arrange
        address = at("global", "EDL")
        bits = numbers_in(quoted("global", "EDL"))[0]
        delays = (1, 1 | 1 << bits, 1 | 1 << (bits - 1))

        # Act
        found = [echo_written(address, delay) for delay in delays]

        # Assert
        self.assertEqual((found[1] == found[0], found[2] == found[0]), (True, False))

    def test_each_coefficient_is_a_tap_shared_by_both_channels(self) -> None:
        # Arrange
        coefficients = MAP["filterCoefficients"]
        taps = numbers_in(coefficients["quote"])[0]

        # Act
        found = [filtered(int(address, 16)) for address in coefficients["addresses"]]

        # Assert
        self.assertEqual(
            [(left == right, left != 0) for left, right in found], [(True, True)] * taps
        )


if __name__ == "__main__":
    unittest.main()
