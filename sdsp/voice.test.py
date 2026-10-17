import json
import random
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sdsp import voice

RECORD = Path(__file__).resolve().parent.parent / "conformance" / "hardware.json"

SEEDS = range(256)


def held(part: voice.Voice) -> dict[str, Any]:
    return {name: getattr(part, name) for name in voice.Voice.__slots__}


def reset_sets() -> dict[str, str]:
    found: dict[str, str] = json.loads(RECORD.read_text())["resetLine"]["sets"]["voice"]
    return found


def every_seed(look: str) -> set[int]:
    return {getattr(voice.Voice(0, seed), look) for seed in SEEDS}


class PowerOnTest(unittest.TestCase):
    def test_one_seed_builds_the_same_voice_twice(self) -> None:
        # Arrange
        first = voice.Voice(3, 0x1234)

        # Act
        second = voice.Voice(3, 0x1234)

        # Assert
        self.assertEqual(held(first), held(second))

    def test_two_seeds_build_two_different_voices(self) -> None:
        # Arrange
        first = voice.Voice(3, 0x1234)

        # Act
        second = voice.Voice(3, 0x4321)

        # Assert
        self.assertNotEqual(held(first), held(second))

    def test_a_voice_comes_up_holding_something_other_than_a_reset_leaves(self) -> None:
        # Arrange
        reset = voice.Voice(0)
        reset.reset()

        # Act
        built = voice.Voice(0)

        # Assert
        self.assertNotEqual(held(built), held(reset))

    def test_both_copies_of_the_decoded_samples_hold_the_same_samples(self) -> None:
        # Arrange
        built = voice.Voice(0, 0x77)

        # Act
        halves = (built.buffer[: voice.BRR_BUFFER], built.buffer[voice.BRR_BUFFER :])

        # Assert
        self.assertEqual(halves[0], halves[1])

    def test_the_decode_position_always_lands_on_a_group_of_four(self) -> None:
        # Arrange
        look = "buffer_position"

        # Act
        found = every_seed(look)

        # Assert
        self.assertEqual(found, {0, 4, 8})

    def test_the_block_offset_always_lands_on_a_pair_inside_the_block(self) -> None:
        # Arrange
        look = "brr_offset"

        # Act
        found = every_seed(look)

        # Assert
        self.assertEqual(found, {1, 3, 5, 7})

    def test_the_key_on_delay_never_starts_beyond_its_own_count(self) -> None:
        # Arrange
        look = "key_on_delay"

        # Act
        found = every_seed(look)

        # Assert
        self.assertEqual(found, set(range(voice.KEY_ON_DELAY + 1)))

    def test_every_envelope_phase_can_be_the_one_a_voice_comes_up_in(self) -> None:
        # Arrange
        look = "envelope_mode"

        # Act
        found = every_seed(look)

        # Assert
        self.assertEqual(found, set(range(voice.ENV_MODES)))

    def test_a_signed_draw_reaches_both_ends_of_its_span(self) -> None:
        # Arrange
        sources = [random.Random(seed) for seed in SEEDS]

        # Act
        found = sorted({voice.signed_draw(source, 4) for source in sources})

        # Assert
        self.assertEqual(found, [-2, -1, 0, 1])


class ResetTest(unittest.TestCase):
    def test_a_reset_sets_every_field_the_record_says_it_sets(self) -> None:
        # Arrange
        part = voice.Voice(5, 0x99)

        # Act
        part.reset()

        # Assert
        self.assertEqual(
            {name: held(part)[name] for name in reset_sets()},
            {
                name: [int(value, 16)] * (voice.BRR_BUFFER * 2)
                if name == "buffer"
                else int(value, 16)
                for name, value in reset_sets().items()
            },
        )

    def test_a_reset_leaves_where_the_voice_is_wired_alone(self) -> None:
        # Arrange
        part = voice.Voice(5, 0x99)

        # Act
        part.reset()

        # Assert
        self.assertEqual((part.index, part.bit, part.base), (5, 0x20, 0x50))


if __name__ == "__main__":
    unittest.main()
