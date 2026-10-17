import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sdsp

SPACE = 0x10000


def contents(memory: sdsp.Memory, size: int) -> list[int]:
    return [memory.read8(address) for address in range(size)]


class ScrambleTest(unittest.TestCase):
    def test_gives_the_requested_length(self) -> None:
        # Arrange
        size = 64

        # Act
        found = sdsp.scramble(size)

        # Assert
        self.assertEqual(len(found), 64)

    def test_repeats_for_one_seed(self) -> None:
        # Arrange
        first = sdsp.scramble(256, seed=7)

        # Act
        second = sdsp.scramble(256, seed=7)

        # Assert
        self.assertEqual(first, second)

    def test_differs_between_seeds(self) -> None:
        # Arrange
        first = sdsp.scramble(256, seed=7)

        # Act
        second = sdsp.scramble(256, seed=8)

        # Assert
        self.assertNotEqual(first, second)

    def test_is_not_a_cleared_machine(self) -> None:
        # Arrange
        size = 4096

        # Act
        found = sdsp.scramble(size)

        # Assert
        self.assertNotEqual(found, bytearray(size))

    def test_covers_most_of_the_byte_range(self) -> None:
        # Arrange
        size = 4096

        # Act
        found = sdsp.scramble(size)

        # Assert
        self.assertGreater(len(set(found)), 200)

    def test_gives_nothing_for_no_length(self) -> None:
        # Arrange
        size = 0

        # Act
        found = sdsp.scramble(size)

        # Assert
        self.assertEqual(found, bytearray())

    def test_the_default_seed_is_the_published_one(self) -> None:
        # Arrange
        published = sdsp.scramble(16, seed=0x5A5A5A5A)

        # Act
        found = sdsp.scramble(16)

        # Assert
        self.assertEqual((found, sdsp.UNSET_SEED), (published, 0x5A5A5A5A))


class SparseMemoryTest(unittest.TestCase):
    def test_reads_back_what_was_written(self) -> None:
        # Arrange
        memory = sdsp.SparseMemory()

        # Act
        memory.write8(0x1234, 0x9C)

        # Assert
        self.assertEqual(memory.read8(0x1234), 0x9C)

    def test_keeps_only_the_low_byte(self) -> None:
        # Arrange
        memory = sdsp.SparseMemory()

        # Act
        memory.write8(0x0010, 0x1FF)

        # Assert
        self.assertEqual(memory.read8(0x0010), 0xFF)

    def test_wraps_the_address_into_the_sixty_four_kilobyte_space(self) -> None:
        # Arrange
        memory = sdsp.SparseMemory()

        # Act
        memory.write8(SPACE + 0x0010, 0x42)

        # Assert
        self.assertEqual(memory.read8(0x0010), 0x42)

    def test_reads_something_it_never_held(self) -> None:
        # Arrange
        memory = sdsp.SparseMemory()

        # Act
        unwritten = {memory.read8(address) for address in range(0, 0x4000, 7)}

        # Assert
        self.assertGreater(len(unwritten), 1)

    def test_repeats_an_unwritten_read(self) -> None:
        # Arrange
        memory = sdsp.SparseMemory(seed=99)

        # Act
        first = memory.read8(0xABCD)

        # Assert
        self.assertEqual(memory.read8(0xABCD), first)

    def test_differs_between_seeds(self) -> None:
        # Arrange
        one = sdsp.SparseMemory(seed=1)
        other = sdsp.SparseMemory(seed=2)

        # Act
        differing = [
            address for address in range(0x400) if one.read8(address) != other.read8(address)
        ]

        # Assert
        self.assertGreater(len(differing), 0x200)

    def test_allocates_only_what_was_written(self) -> None:
        # Arrange
        memory = sdsp.SparseMemory()
        memory.read8(0x1000)

        # Act
        memory.write8(0x2000, 1)

        # Assert
        self.assertEqual(memory.cells, {0x2000: 1})

    def test_a_written_zero_stays_zero(self) -> None:
        # Arrange
        memory = sdsp.SparseMemory()
        address = next(a for a in range(0x1000) if memory.read8(a) != 0)

        # Act
        memory.write8(address, 0)

        # Assert
        self.assertEqual(memory.read8(address), 0)


class MemoryTest(unittest.TestCase):
    def test_is_scrambled_when_nothing_is_asked_for(self) -> None:
        # Arrange
        size = 0x1000

        # Act
        memory = sdsp.Memory(size=size)

        # Assert
        self.assertNotEqual(set(contents(memory, size)), {0})

    def test_fills_with_a_byte(self) -> None:
        # Arrange
        size = 0x100

        # Act
        memory = sdsp.Memory(size=size, fill=0xAA)

        # Assert
        self.assertEqual(set(contents(memory, size)), {0xAA})

    def test_keeps_only_the_low_byte_of_the_fill(self) -> None:
        # Arrange
        size = 0x10

        # Act
        memory = sdsp.Memory(size=size, fill=0x1BB)

        # Assert
        self.assertEqual(set(contents(memory, size)), {0xBB})

    def test_zero_is_a_decision_a_caller_can_make(self) -> None:
        # Arrange
        size = 0x100

        # Act
        memory = sdsp.Memory(size=size, fill=0)

        # Assert
        self.assertEqual(set(contents(memory, size)), {0})

    def test_takes_an_image_at_the_bottom_and_pads_the_rest(self) -> None:
        # Arrange
        image = b"\x01\x02\x03"

        # Act
        memory = sdsp.Memory(size=0x10, fill=image)

        # Assert
        self.assertEqual(contents(memory, 0x10), [1, 2, 3] + [0] * 0x0D)

    def test_repeats_for_one_seed(self) -> None:
        # Arrange
        first = contents(sdsp.Memory(size=0x100, seed=3), 0x100)

        # Act
        second = contents(sdsp.Memory(size=0x100, seed=3), 0x100)

        # Assert
        self.assertEqual(first, second)

    def test_scrambles_from_the_seed_it_is_given(self) -> None:
        # Arrange
        seed = 3

        # Act
        memory = sdsp.Memory(size=0x100, seed=seed)

        # Assert
        self.assertEqual(bytes(contents(memory, 0x100)), bytes(sdsp.scramble(0x100, seed)))

    def test_reads_back_what_was_written(self) -> None:
        # Arrange
        memory = sdsp.Memory(fill=0)

        # Act
        memory.write8(0x1234, 0x5A)

        # Assert
        self.assertEqual(memory.read8(0x1234), 0x5A)

    def test_defaults_to_the_whole_address_space(self) -> None:
        # Arrange
        memory = sdsp.Memory(fill=0)

        # Act
        memory.write8(0xFFFF, 0x66)

        # Assert
        self.assertEqual(memory.read8(0xFFFF), 0x66)

    def test_wraps_the_address_into_the_sixty_four_kilobyte_space(self) -> None:
        # Arrange
        memory = sdsp.Memory(fill=0)

        # Act
        memory.write8(SPACE + 0x0020, 0x77)

        # Assert
        self.assertEqual(memory.read8(0x0020), 0x77)


if __name__ == "__main__":
    unittest.main()
