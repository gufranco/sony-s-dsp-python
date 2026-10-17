import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.register_rig import (
    DIRECTORY,
    LOUD,
    QUIET,
    SETTLE,
    SHORT,
    a_memory,
    a_part,
    a_volume_silences,
    an_entry,
    at,
    consumed,
    each_sample,
    keyed,
    moved,
    numbers_in,
    quoted,
    record,
    register_map,
    silent,
    voiced,
)
from sdsp import core

FACTS = record()
MAP = register_map()


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


if __name__ == "__main__":
    unittest.main()
