import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sdsp import core, echo, state
from sdsp.memory import Memory


class EchoAddressTest(unittest.TestCase):
    def test_the_right_channel_sits_two_bytes_after_the_left(self) -> None:
        # Arrange
        chip = core.Chip(Memory(fill=0)).reset()
        chip.echo_pointer = 0x4000

        # Act
        found = chip._echo_address(1)

        # Assert
        self.assertEqual(found, 0x4002)

    def test_and_wraps_at_the_top_of_audio_memory(self) -> None:
        # Arrange
        chip = core.Chip(Memory(fill=0)).reset()
        chip.echo_pointer = 0xFFFF

        # Act
        found = chip._echo_address(1)

        # Assert
        self.assertEqual(found, 0x0001)


class EchoLengthTest(unittest.TestCase):
    def test_the_delay_counts_only_the_low_four_bits_of_its_register(self) -> None:
        # Arrange
        chip = core.Chip(Memory(fill=0)).reset()
        chip.write(echo.REG_EDL, 0xF3)

        # Act
        chip.echo_29()

        # Assert
        self.assertEqual(chip.echo_length, 3 * state.ECHO_DELAY_STEP)


if __name__ == "__main__":
    unittest.main()
