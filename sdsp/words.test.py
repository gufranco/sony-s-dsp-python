import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sdsp
from conformance.register_rig import Part

DIRECTORY_PAGE = 0x02
SOURCE = 0x0300
ECHO_PAGE = 0x40
ECHO_BYTES = 0x800
LOUD = 0x7F
UNITY_PITCH_HIGH = 0x10
ECHO_WRITES_OFF = 0x20
ONE_LOOPING_BLOCK = 0xB3
POSITIVE_SEVENS = 0x77
NEGATIVE_SEVENS = 0x99
SETTLED = 8

MVOLL = 0x0C
MVOLR = 0x1C
EVOLL = 0x2C
EVOLR = 0x3C
KON = 0x4C
DIR = 0x5D
FLG = 0x6C
ESA = 0x6D
EDL = 0x7D
FIR_OLDEST = 0x0F

VOLL = 0x00
VOLR = 0x01
PITCHH = 0x03
GAIN = 0x07

TOP = 0x7FFF * LOUD >> 7
BOTTOM = -0x8000 * LOUD >> 7


def one_steady_block(nybbles: int) -> sdsp.Memory:
    memory = sdsp.Memory(fill=0)
    for offset, value in enumerate(SOURCE.to_bytes(2, "little") * 2):
        memory.write8(DIRECTORY_PAGE * 0x100 + offset, value)
    memory.write8(SOURCE, ONE_LOOPING_BLOCK)
    for offset in range(1, 9):
        memory.write8(SOURCE + offset, nybbles)
    return memory


def voices_playing(count: int, nybbles: int = POSITIVE_SEVENS, volume: int = LOUD) -> Part:
    part = sdsp.Chip("s-dsp", one_steady_block(nybbles)).reset()
    for voice in part.voices[:count]:
        part.write(voice.base + VOLL, volume)
        part.write(voice.base + VOLR, volume)
        part.write(voice.base + PITCHH, UNITY_PITCH_HIGH)
        part.write(voice.base + GAIN, LOUD)
    for register, value in {MVOLL: LOUD, MVOLR: LOUD, DIR: DIRECTORY_PAGE}.items():
        part.write(register, value)
    part.write(FLG, ECHO_WRITES_OFF)
    part.write(KON, (1 << count) - 1)
    return part


def echoing_a_word(word: int) -> Part:
    memory = sdsp.Memory(fill=0)
    for address in range(ECHO_PAGE * 0x100, ECHO_PAGE * 0x100 + ECHO_BYTES, 2):
        memory.write8(address, word & 0xFF)
        memory.write8(address + 1, word >> 8)
    part = sdsp.Chip("s-dsp", memory).reset()
    for register, value in {EVOLL: LOUD, EVOLR: LOUD, ESA: ECHO_PAGE, EDL: 1}.items():
        part.write(register, value)
    part.write(FIR_OLDEST, LOUD)
    part.write(FLG, ECHO_WRITES_OFF)
    return part


def settled(rendered: list[int]) -> set[int]:
    return set(rendered[SETTLED * 2 :])


class ClampTest(unittest.TestCase):
    def test_clamping_leaves_a_mix_that_already_fits_as_the_sum_of_its_voices(self) -> None:
        # Arrange
        (alone,) = settled(voices_playing(1).render(16))

        # Act
        (pair,) = settled(voices_playing(2).render(16))

        # Assert
        self.assertLess(abs(pair - 2 * alone), 2)
        self.assertLess(pair, TOP)

    def test_clamping_stops_at_the_top_of_the_range(self) -> None:
        # Arrange
        every_voice = voices_playing(8)

        # Act
        found = settled(every_voice.render(16))

        # Assert
        self.assertEqual(found, {TOP})

    def test_clamping_stops_at_the_bottom_of_the_range(self) -> None:
        # Arrange
        every_voice = voices_playing(8, NEGATIVE_SEVENS)

        # Act
        found = settled(every_voice.render(16))

        # Assert
        self.assertEqual(found, {BOTTOM})

    def test_a_mix_past_the_top_stays_there_however_many_voices_add_to_it(self) -> None:
        # Arrange
        three = settled(voices_playing(3).render(16))

        # Act
        eight = settled(voices_playing(8).render(16))

        # Assert
        self.assertEqual(three, eight)


class SignedTest(unittest.TestCase):
    def test_a_volume_byte_with_its_top_bit_set_reads_as_negative(self) -> None:
        # Arrange
        part = voices_playing(1, volume=0x80)

        # Act
        found = settled(part.render(16))

        # Assert
        self.assertLess(max(found), 0)

    def test_a_volume_byte_just_below_it_reads_as_positive(self) -> None:
        # Arrange
        part = voices_playing(1, volume=0x7F)

        # Act
        found = settled(part.render(16))

        # Assert
        self.assertGreater(min(found), 0)

    def test_a_word_in_the_echo_buffer_with_its_top_bit_set_reads_as_negative(self) -> None:
        # Arrange
        part = echoing_a_word(0x8000)

        # Act
        found = settled(part.render(16))

        # Assert
        self.assertLess(max(found), 0)

    def test_a_word_just_below_it_reads_as_positive(self) -> None:
        # Arrange
        part = echoing_a_word(0x7FFF)

        # Act
        found = settled(part.render(16))

        # Assert
        self.assertGreater(min(found), 0)


if __name__ == "__main__":
    unittest.main()
