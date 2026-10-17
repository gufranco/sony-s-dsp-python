import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sdsp
from conformance.register_rig import Part, Store

UNTOUCHED = 0xAA
DIRECTORY_PAGE = 0x20
SOURCE = 0x2100
ECHO_PAGE = 0x40
TOP_PAGE = 0xFF
DELAY_STEP = 0x800
LOUD = 0x7F
UNITY_PITCH_HIGH = 0x10
ONE_LOOPING_BLOCK = 0xB3
STEADY = 0x77
ECHO_WRITES_ON = 0x00

VOLL = 0x00
VOLR = 0x01
PITCHH = 0x03
GAIN = 0x07
KON = 0x4C
EON = 0x4D
DIR = 0x5D
FLG = 0x6C
ESA = 0x6D
EDL = 0x7D


def audio_ram() -> sdsp.Memory:
    memory = sdsp.Memory(fill=UNTOUCHED)
    for offset, value in enumerate(SOURCE.to_bytes(2, "little") * 2):
        memory.write8(DIRECTORY_PAGE * 0x100 + offset, value)
    memory.write8(SOURCE, ONE_LOOPING_BLOCK)
    for offset in range(1, 9):
        memory.write8(SOURCE + offset, STEADY)
    return memory


def echoing(page: int, delay: int, left: int = LOUD, right: int = LOUD) -> Part:
    part = sdsp.Chip("s-dsp", audio_ram()).reset()
    voice = part.voices[0]
    for offset, value in {VOLL: left, VOLR: right, PITCHH: UNITY_PITCH_HIGH, GAIN: LOUD}.items():
        part.write(voice.base + offset, value)
    for register, value in {DIR: DIRECTORY_PAGE, EON: voice.bit, ESA: page, EDL: delay}.items():
        part.write(register, value)
    part.write(FLG, ECHO_WRITES_ON)
    part.write(KON, voice.bit)
    return part


def words_at(memory: Store, address: int) -> tuple[int, int]:
    def word(at: int) -> int:
        return memory.read8(at) | memory.read8((at + 1) & 0xFFFF) << 8

    return word(address), word(address + 2)


def written(memory: Store, start: int, length: int) -> list[int]:
    return [
        address
        for address in range(start, start + length)
        if memory.read8(address & 0xFFFF) != UNTOUCHED
    ]


class EchoAddressTest(unittest.TestCase):
    def test_the_left_channel_is_the_first_word_of_each_pair(self) -> None:
        # Arrange
        part = echoing(ECHO_PAGE, 0, right=0)

        # Act
        part.render(32)

        # Assert
        left, right = words_at(part.memory, ECHO_PAGE * 0x100)
        self.assertEqual((left != 0, right), (True, 0))

    def test_the_right_channel_sits_two_bytes_after_the_left(self) -> None:
        # Arrange
        mirror = echoing(ECHO_PAGE, 0, right=0)
        mirror.render(32)
        (left_alone, _) = words_at(mirror.memory, ECHO_PAGE * 0x100)
        part = echoing(ECHO_PAGE, 0, left=0)

        # Act
        part.render(32)

        # Assert
        self.assertEqual(words_at(part.memory, ECHO_PAGE * 0x100), (0, left_alone))

    def test_and_the_region_wraps_from_the_top_of_audio_memory_to_the_bottom(self) -> None:
        # Arrange
        part = echoing(TOP_PAGE, 1)

        # Act
        part.render(DELAY_STEP // 4 + 8)

        # Assert
        self.assertEqual(
            written(part.memory, TOP_PAGE * 0x100, DELAY_STEP),
            list(range(TOP_PAGE * 0x100, TOP_PAGE * 0x100 + DELAY_STEP)),
        )


class EchoLengthTest(unittest.TestCase):
    def test_the_delay_counts_only_the_low_four_bits_of_its_register(self) -> None:
        # Arrange
        part = echoing(ECHO_PAGE, 0xF1)

        # Act
        part.render(DELAY_STEP // 4 + 8)

        # Assert
        self.assertEqual(
            written(part.memory, ECHO_PAGE * 0x100, 2 * DELAY_STEP),
            list(range(ECHO_PAGE * 0x100, ECHO_PAGE * 0x100 + DELAY_STEP)),
        )


if __name__ == "__main__":
    unittest.main()
