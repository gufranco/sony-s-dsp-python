import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sdsp.memory import ADDRESS_MASK, UNSET_SEED, Memory, SparseMemory, scramble


class ScrambleTest(unittest.TestCase):
    def test_gives_the_requested_length(self):
        self.assertEqual(len(scramble(64)), 64)

    def test_repeats_for_one_seed(self):
        self.assertEqual(scramble(256, seed=7), scramble(256, seed=7))

    def test_differs_between_seeds(self):
        self.assertNotEqual(scramble(256, seed=7), scramble(256, seed=8))

    def test_is_not_a_cleared_machine(self):
        self.assertNotEqual(scramble(4096), bytearray(4096))

    def test_covers_most_of_the_byte_range(self):
        self.assertGreater(len(set(scramble(4096))), 200)

    def test_gives_nothing_for_no_length(self):
        self.assertEqual(scramble(0), bytearray())


class AddressSpaceTest(unittest.TestCase):
    def test_the_space_is_sixty_four_kilobytes(self):
        self.assertEqual(ADDRESS_MASK, 0xFFFF)


class SparseMemoryTest(unittest.TestCase):
    def test_reads_back_what_was_written(self):
        memory = SparseMemory()

        memory.write8(0x1234, 0x9C)

        self.assertEqual(memory.read8(0x1234), 0x9C)

    def test_keeps_only_the_low_byte(self):
        memory = SparseMemory()

        memory.write8(0x0010, 0x1FF)

        self.assertEqual(memory.read8(0x0010), 0xFF)

    def test_wraps_the_address_into_the_space(self):
        memory = SparseMemory()

        memory.write8(0x10010, 0x42)

        self.assertEqual(memory.read8(0x0010), 0x42)

    def test_reads_something_it_never_held(self):
        memory = SparseMemory()

        unwritten = {memory.read8(address) for address in range(0, 0x4000, 7)}

        self.assertGreater(len(unwritten), 1)

    def test_repeats_an_unwritten_read(self):
        memory = SparseMemory(seed=99)

        self.assertEqual(memory.read8(0xABCD), memory.read8(0xABCD))

    def test_differs_between_seeds(self):
        one = SparseMemory(seed=1)
        other = SparseMemory(seed=2)

        differing = [
            address for address in range(0x400) if one.read8(address) != other.read8(address)
        ]

        self.assertGreater(len(differing), 0x200)

    def test_allocates_only_what_was_written(self):
        memory = SparseMemory()

        memory.read8(0x1000)
        memory.write8(0x2000, 1)

        self.assertEqual(len(memory.cells), 1)

    def test_a_written_zero_stays_zero(self):
        memory = SparseMemory()
        address = next(a for a in range(0x1000) if memory.read8(a) != 0)

        memory.write8(address, 0)

        self.assertEqual(memory.read8(address), 0)


class MemoryTest(unittest.TestCase):
    def test_is_scrambled_when_nothing_is_asked_for(self):
        self.assertNotEqual(Memory(size=0x1000).data, bytearray(0x1000))

    def test_fills_with_a_byte(self):
        self.assertEqual(set(Memory(size=0x100, fill=0xAA).data), {0xAA})

    def test_keeps_only_the_low_byte_of_the_fill(self):
        self.assertEqual(set(Memory(size=0x10, fill=0x1BB).data), {0xBB})

    def test_zero_is_a_decision_a_caller_can_make(self):
        self.assertEqual(Memory(size=0x100, fill=0).data, bytearray(0x100))

    def test_takes_an_image_at_the_bottom(self):
        memory = Memory(size=0x100, fill=b"\x01\x02\x03")

        self.assertEqual(bytes(memory.data[:3]), b"\x01\x02\x03")

    def test_pads_the_rest_of_an_image(self):
        self.assertEqual(Memory(size=0x10, fill=b"\xff").data[1:], bytearray(0x0F))

    def test_repeats_for_one_seed(self):
        self.assertEqual(Memory(size=0x100, seed=3).data, Memory(size=0x100, seed=3).data)

    def test_reads_back_what_was_written(self):
        memory = Memory(fill=0)

        memory.write8(0x1234, 0x5A)

        self.assertEqual(memory.read8(0x1234), 0x5A)

    def test_defaults_to_the_whole_address_space(self):
        self.assertEqual(len(Memory().data), 0x10000)

    def test_wraps_the_address_into_the_space(self):
        memory = Memory(fill=0)

        memory.write8(0x10020, 0x77)

        self.assertEqual(memory.read8(0x0020), 0x77)


class SeedTest(unittest.TestCase):
    def test_the_default_seed_is_shared(self):
        self.assertEqual(scramble(16), scramble(16, seed=UNSET_SEED))


if __name__ == "__main__":
    unittest.main()
