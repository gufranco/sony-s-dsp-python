import json
import random
import sys
import unittest
from pathlib import Path
from typing import Any, override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sdsp import core, state
from sdsp.memory import Memory
from sdsp.voice import Voice

RECORD = Path(__file__).resolve().parent.parent / "conformance" / "hardware.json"


CYCLE = 0x7FFF


def record() -> dict[str, Any]:
    found: dict[str, Any] = json.loads(RECORD.read_text())
    return found


def held(chip: core.Chip) -> dict[str, Any]:
    found = {name: getattr(chip, name) for name in state.State.__slots__ if name != "voices"}
    found["voices"] = [[getattr(voice, name) for name in Voice.__slots__] for voice in chip.voices]
    return found


def a_part(seed: int = 0x1234) -> core.Chip:
    return core.Chip(Memory(fill=0), seed=seed)


class LowestDraws(random.Random):
    @override
    def randrange(self, start: int, stop: int | None = None, step: int = 1) -> int:
        return 0 if stop is None else start

    @override
    def randbytes(self, n: int) -> bytes:
        return bytes(n)

    @override
    def getrandbits(self, k: int) -> int:
        return 0


class HighestDraws(LowestDraws):
    @override
    def randrange(self, start: int, stop: int | None = None, step: int = 1) -> int:
        return start - 1 if stop is None else stop - 1


def powered_by(draws: random.Random) -> core.Chip:
    chip = a_part()
    chip._power_on(draws)
    return chip


def filled(held: Any, value: int) -> Any:
    if isinstance(held, list):
        return [filled(one, value) for one in held]
    return value


def cycle_length(start: int) -> int:
    value = state.next_noise(start)
    steps = 1
    while value != start and steps <= CYCLE:
        value = state.next_noise(value)
        steps += 1
    return steps


class PowerOnTest(unittest.TestCase):
    def test_one_seed_brings_the_part_up_the_same_way_twice(self) -> None:
        # Arrange
        first = a_part()

        # Act
        second = a_part()

        # Assert
        self.assertEqual(held(first), held(second))

    def test_every_field_follows_the_seed(self) -> None:
        # Arrange
        seeds = range(16)

        # Act
        built = [held(a_part(seed)) for seed in seeds]

        # Assert
        self.assertEqual(
            [name for name in built[0] if all(one[name] == built[0][name] for one in built)], []
        )

    def test_nothing_comes_up_holding_what_a_reset_leaves_whatever_the_seed(self) -> None:
        # Arrange
        reset = held(a_part().reset())

        # Act
        built = [held(a_part(seed)) for seed in range(16)]

        # Assert
        self.assertEqual(
            [name for name in reset if all(one[name] == reset[name] for one in built)], []
        )

    def test_the_noise_generator_never_comes_up_holding_what_it_cannot_leave(self) -> None:
        # Arrange
        never = int(record()["powerOn"]["noiseNeverHolds"], 16)

        # Act
        chip = powered_by(LowestDraws())

        # Assert
        self.assertNotEqual(chip.noise, never)

    def test_and_never_comes_up_wider_than_its_fifteen_bits(self) -> None:
        # Arrange
        draws = HighestDraws()

        # Act
        chip = powered_by(draws)

        # Assert
        self.assertEqual(chip.noise, CYCLE)

    def test_the_value_the_record_excludes_is_one_the_generator_cannot_leave(self) -> None:
        # Arrange
        never = int(record()["powerOn"]["noiseNeverHolds"], 16)

        # Act
        found = state.next_noise(never)

        # Assert
        self.assertEqual(found, never)

    def test_and_every_other_value_lies_on_one_cycle_through_all_of_them(self) -> None:
        # Arrange
        start = state.NOISE_RESET

        # Act
        found = cycle_length(start)

        # Assert
        self.assertEqual(found, CYCLE)

    def test_both_copies_of_the_echo_history_hold_the_same_samples(self) -> None:
        # Arrange
        chip = a_part(0x77)

        # Act
        halves = (chip.echo_history[: state.ECHO_HISTORY], chip.echo_history[state.ECHO_HISTORY :])

        # Assert
        self.assertEqual(halves[0], halves[1])

    def test_every_voice_comes_up_its_own_way(self) -> None:
        # Arrange
        chip = a_part()

        # Act
        buffers = {tuple(voice.buffer) for voice in chip.voices}

        # Assert
        self.assertEqual(len(buffers), state.VOICE_COUNT)

    def test_a_part_nobody_reset_still_runs_from_wherever_it_came_up(self) -> None:
        # Arrange
        chips = [a_part(seed) for seed in range(64)]

        # Act
        rendered = [len(chip.render(4)) for chip in chips]

        # Assert
        self.assertEqual(set(rendered), {8})


class ResetTest(unittest.TestCase):
    def sets(self) -> dict[str, Any]:
        found: dict[str, Any] = record()["resetLine"]["sets"]
        return found

    def test_a_reset_sets_every_register_the_record_says_it_sets(self) -> None:
        # Arrange
        chip = a_part()
        expected = bytearray([int(self.sets()["registers"], 16)]) * state.REGISTER_COUNT
        expected[state.REG_FLG] = int(self.sets()["FLG"], 16)

        # Act
        chip.reset()

        # Assert
        self.assertEqual(chip.registers, expected)

    def test_a_reset_sets_every_latch_the_record_says_it_sets(self) -> None:
        # Arrange
        chip = a_part()
        sets = self.sets()["chip"]

        # Act
        chip.reset()

        # Assert
        self.assertEqual(
            {name: held(chip)[name] for name in sets},
            {name: filled(held(chip)[name], int(sets[name], 16)) for name in sets},
        )

    def test_and_those_are_every_latch_the_part_holds(self) -> None:
        # Arrange
        sets = self.sets()["chip"]

        # Act
        latches = set(held(a_part())) - {"registers", "voices"}

        # Assert
        self.assertEqual(latches, set(sets))

    def test_a_reset_leaves_memory_and_what_was_rendered_alone(self) -> None:
        # Arrange
        chip = a_part()
        chip.rendered = [1, 2]
        chip.memory.write8(0x1234, 0x56)

        # Act
        chip.reset()

        # Assert
        self.assertEqual((chip.rendered, chip.memory.read8(0x1234)), ([1, 2], 0x56))


if __name__ == "__main__":
    unittest.main()
