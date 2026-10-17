import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.register_rig import (
    DIRECTORY,
    SHORT,
    SOURCE,
    a_memory,
    a_part,
    a_sample,
    a_volume_silences,
    at,
    consumed,
    each_sample,
    keyed,
    moved,
    numbers_in,
    own_side_and_other,
    quoted,
    record,
    side_of,
    silent,
)
from sdsp import core, state
from sdsp.memory import Memory
from sdsp.voice import Voice


class RecordTest(unittest.TestCase):
    def test_the_record_is_read_once_and_handed_back_each_time(self) -> None:
        # Arrange
        first = record()

        # Act
        second = record()

        # Assert
        self.assertIs(first, second)

    def test_a_register_is_found_at_the_address_the_map_prints(self) -> None:
        # Arrange
        name = "FLG"

        # Act
        found = at("global", name)

        # Assert
        self.assertEqual(found, 0x6C)

    def test_a_register_is_found_by_its_function_quote(self) -> None:
        # Arrange
        name = "FLG"

        # Act
        found = quoted("global", name)

        # Assert
        self.assertEqual(found, "Designated on/off of reset, mute, echo, and noise clock")


class TextTest(unittest.TestCase):
    def test_every_number_in_a_sentence_is_read_in_order(self) -> None:
        # Arrange
        text = "bits 0 ~ 7 are voices 0 ~ 7"

        # Act
        found = numbers_in(text)

        # Assert
        self.assertEqual(found, [0, 7, 0, 7])

    def test_a_sentence_names_the_channel_it_reaches(self) -> None:
        # Arrange
        texts = ("Left channel volume", "Volume (R)")

        # Act
        found = [side_of(text) for text in texts]

        # Assert
        self.assertEqual(found, [0, 1])


class MemoryLayoutTest(unittest.TestCase):
    def test_the_last_block_of_a_sample_carries_the_end_and_loop_flags(self) -> None:
        # Arrange
        memory = Memory(fill=0)

        # Act
        a_sample(memory, 0x0300, lambda: 0x11, 3)

        # Assert
        self.assertEqual(
            [memory.read8(0x0300 + block * core.BRR_BLOCK_BYTES) for block in range(3)],
            [0xC0, 0xC0, 0xC3],
        )

    def test_each_directory_entry_points_at_its_sample_twice(self) -> None:
        # Arrange
        entry = DIRECTORY * 0x100 + 3 * 4

        # Act
        memory = a_memory()

        # Assert
        self.assertEqual([memory.read8(entry + n) for n in range(4)], [0x00, 0x22, 0x00, 0x22])


class PartTest(unittest.TestCase):
    def test_a_part_is_reset_and_left_with_echo_writes_off(self) -> None:
        # Arrange
        memory = a_memory()

        # Act
        chip = a_part(memory)

        # Assert
        self.assertEqual((chip.read(state.REG_FLG), chip.read(core.REG_DIR)), (0x20, DIRECTORY))

    def test_keying_arms_only_the_voices_named(self) -> None:
        # Arrange
        chip = a_part()

        # Act
        keyed(chip, 0x05)

        # Assert
        self.assertEqual(chip.new_kon, 0x05)

    def test_a_voice_one_block_and_two_pairs_in_has_consumed_twenty_samples(self) -> None:
        # Arrange
        voice = Voice(0)
        voice.brr_address = SOURCE + core.BRR_BLOCK_BYTES
        voice.brr_offset = 3

        # Act
        found = consumed(voice)

        # Assert
        self.assertEqual(found, 20)

    def test_a_look_is_taken_once_per_sample(self) -> None:
        # Arrange
        chip = a_part()

        # Act
        found = each_sample(chip, 3, lambda: chip.phase)

        # Assert
        self.assertEqual(found, [0, 0, 0])

    def test_no_clock_moves_no_register(self) -> None:
        # Arrange
        chip = a_part()

        # Act
        found = moved(chip, 0)

        # Assert
        self.assertEqual(found, set())

    def test_the_short_sample_sits_where_the_layout_says(self) -> None:
        # Arrange
        memory = a_memory()

        # Act
        header = memory.read8(SHORT + core.BRR_BLOCK_BYTES)

        # Assert
        self.assertEqual(header, 0xC3)


class SilenceTest(unittest.TestCase):
    def test_only_zero_is_silence(self) -> None:
        # Arrange
        samples = ([0, 0, 0], [0, 1, 0])

        # Act
        found = [silent(list(one)) for one in samples]

        # Assert
        self.assertEqual(found, [True, False])

    def test_the_named_side_is_read_from_the_interleaved_pairs(self) -> None:
        # Arrange
        rendered = [0, 5, 0, 7]

        # Act
        found = own_side_and_other(rendered, "Left")

        # Assert
        self.assertEqual(found, [True, False])

    def test_zeroing_the_left_voice_volume_silences_the_left_channel_alone(self) -> None:
        # Arrange
        address = core.V_VOLL

        # Act
        found = a_volume_silences(address, "Left")

        # Assert
        self.assertEqual(found, [True, False])


if __name__ == "__main__":
    unittest.main()
