import json
import random
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sdsp
from conformance.register_rig import Part

RECORD = Path(__file__).resolve().parent.parent / "conformance" / "hardware.json"

NOISE_CYCLE = 32767

NOISE_CYCLE_FACTORS = (7, 31, 151)

SEEDS = range(16)

BUSY_SEEDS = (0x63, 1, 2, 3)

VOICE_FIELDS = (
    "brr_address",
    "brr_offset",
    "buffer",
    "buffer_position",
    "interpolation",
    "envelope",
    "hidden_envelope",
    "envelope_mode",
    "envelope_out",
    "key_on_delay",
)

BRR_BLOCK_BYTES = 9
DIRECTORY_PAGE = 0x02
SOURCES = 0x1000
ECHO_PAGE = 0x60
ECHO_DELAY = 0x0F
ECHO_SPAN = ECHO_DELAY * 0x800

VOLL = 0x00
VOLR = 0x01
PITCHL = 0x02
PITCHH = 0x03
SRCN = 0x04
ADSR1 = 0x05
ADSR2 = 0x06
GAIN = 0x07
OUTX = 0x09
MVOLL = 0x0C
EFB = 0x0D
FIR = 0x0F
MVOLR = 0x1C
EVOLL = 0x2C
PMON = 0x2D
EVOLR = 0x3C
NON = 0x3D
KON = 0x4C
EON = 0x4D
KOFF = 0x5C
DIR = 0x5D
FLG = 0x6C
ESA = 0x6D
EDL = 0x7D

ECHO_WRITES_OFF = 0x20
NOISE_EVERY_SAMPLE = 0x1F
LOUD = 0x7F


def record() -> dict[str, Any]:
    found: dict[str, Any] = json.loads(RECORD.read_text())
    return found


def observed(chip: Part) -> dict[str, Any]:
    return {
        "registers": bytes(chip.registers),
        "phase": chip.phase,
        "voices": [[getattr(voice, name) for name in VOICE_FIELDS] for voice in chip.voices],
    }


def a_part(seed: int = 0x1234) -> Part:
    return sdsp.Chip("s-dsp", sdsp.Memory(fill=0), seed=seed)


def busy_memory() -> sdsp.Memory:
    rng = random.Random(11)
    memory = sdsp.Memory(fill=0)
    for source in range(4):
        start = SOURCES + source * 0x100
        for block in range(8):
            base = start + block * BRR_BLOCK_BYTES
            memory.write8(base, (rng.randrange(13) << 4) | (rng.randrange(4) << 2))
            for offset in range(1, BRR_BLOCK_BYTES):
                memory.write8(base + offset, rng.randrange(256))
        last = start + 7 * BRR_BLOCK_BYTES
        memory.write8(last, memory.read8(last) | 0x03)
        for index, value in enumerate(start.to_bytes(2, "little") * 2):
            memory.write8(DIRECTORY_PAGE * 0x100 + source * 4 + index, value)
    for address in range(ECHO_PAGE * 0x100, ECHO_PAGE * 0x100 + ECHO_SPAN):
        memory.write8(address, rng.randrange(256))
    return memory


def busy(chip: Part) -> Part:
    rng = random.Random(5)
    for voice in chip.voices:
        settings = {
            VOLL: rng.randrange(0x40, 0x80),
            VOLR: rng.randrange(0x40, 0x80),
            PITCHL: rng.randrange(256),
            PITCHH: rng.randrange(0x08, 0x20),
            SRCN: voice.index % 4,
            ADSR1: 0x80 | rng.randrange(256),
            ADSR2: rng.randrange(256),
            GAIN: rng.randrange(256),
        }
        for offset, value in settings.items():
            chip.write(voice.base + offset, value)
        chip.write(voice.base + FIR, rng.randrange(-0x20, 0x20) & 0xFF)
    settings = {
        MVOLL: LOUD,
        MVOLR: LOUD,
        EVOLL: 0x40,
        EVOLR: 0x40,
        EFB: 0x30,
        PMON: 0x0A,
        NON: 0x30,
        EON: 0xC3,
        KOFF: 0,
        DIR: DIRECTORY_PAGE,
        ESA: ECHO_PAGE,
        EDL: ECHO_DELAY,
        FLG: 0x1A,
        KON: 0xFF,
    }
    for register, value in settings.items():
        chip.write(register, value)
    return chip


def run_busy(seed: int) -> tuple[list[int], dict[str, Any], bytes]:
    chip = busy(sdsp.Chip("s-dsp", busy_memory(), seed=seed).reset())
    rendered = chip.render(400)
    return rendered, observed(chip), bytes(chip.memory.read8(at) for at in range(0x10000))


def noise_on_voice_zero(chip: Part, flags: int) -> Part:
    voice = chip.voices[0].base
    for offset, value in {VOLL: LOUD, VOLR: LOUD, ADSR1: 0, GAIN: LOUD}.items():
        chip.write(voice + offset, value)
    for register, value in {NON: 0x01, PMON: 0, KOFF: 0, FLG: flags, KON: 0x01}.items():
        chip.write(register, value)
    chip.run(2 * 32)
    chip.write(KON, 0x01)
    return chip


def outx_each_sample(chip: Part, samples: int) -> list[int]:
    found = []
    for _ in range(samples):
        chip.run(32)
        found.append(chip.read(OUTX))
    return found


class PowerOnTest(unittest.TestCase):
    def test_one_seed_brings_the_part_up_the_same_way_twice(self) -> None:
        # Arrange
        first = a_part()

        # Act
        second = a_part()

        # Assert
        self.assertEqual((observed(first), first.render(8)), (observed(second), second.render(8)))

    def test_everything_the_part_shows_follows_the_seed(self) -> None:
        # Arrange
        seeds = SEEDS

        # Act
        built = [observed(a_part(seed)) for seed in seeds]

        # Assert
        self.assertEqual(
            [name for name in built[0] if all(one[name] == built[0][name] for one in built)], []
        )

    def test_nothing_comes_up_holding_what_a_reset_leaves_whatever_the_seed(self) -> None:
        # Arrange
        reset = observed(a_part().reset())

        # Act
        built = [observed(a_part(seed)) for seed in SEEDS]

        # Assert
        self.assertEqual(
            [name for name in reset if all(one[name] == reset[name] for one in built)], []
        )

    def test_the_noise_generator_never_comes_up_holding_what_it_cannot_leave(self) -> None:
        # Arrange
        never = int(record()["powerOn"]["noiseNeverHolds"], 16)
        parts = [noise_on_voice_zero(a_part(seed), ECHO_WRITES_OFF) for seed in range(64)]

        # Act
        frozen = [set(outx_each_sample(part, 16)[8:]) for part in parts]

        # Assert
        self.assertEqual([held for held in frozen if held == {never * 2}], [])

    def test_and_every_value_it_comes_up_holding_lies_on_one_cycle_of_the_printed_length(
        self,
    ) -> None:
        # Arrange
        part = noise_on_voice_zero(a_part(0x77), ECHO_WRITES_OFF | NOISE_EVERY_SAMPLE)
        part.run(8 * 32)
        shortest = NOISE_CYCLE // min(NOISE_CYCLE_FACTORS)

        # Act
        stream = outx_each_sample(part, NOISE_CYCLE + shortest)

        # Assert
        self.assertEqual(
            (
                stream[:shortest] == stream[NOISE_CYCLE:],
                [
                    stream[: NOISE_CYCLE - NOISE_CYCLE // factor]
                    == stream[NOISE_CYCLE // factor : NOISE_CYCLE]
                    for factor in NOISE_CYCLE_FACTORS
                ],
            ),
            (True, [False, False, False]),
        )

    def test_every_voice_comes_up_its_own_way(self) -> None:
        # Arrange
        chip = a_part()

        # Act
        buffers = {tuple(voice.buffer) for voice in chip.voices}

        # Assert
        self.assertEqual(len(buffers), 8)

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
        expected = bytearray([int(self.sets()["registers"], 16)]) * 128
        expected[FLG] = int(self.sets()["FLG"], 16)

        # Act
        chip.reset()

        # Assert
        self.assertEqual(chip.registers, expected)

    def test_a_reset_puts_the_schedule_back_at_its_first_clock(self) -> None:
        # Arrange
        chip = a_part()
        chip.run(5)

        # Act
        chip.reset()

        # Assert
        self.assertEqual(chip.phase, int(self.sets()["chip"]["phase"], 16))

    def test_after_a_reset_parts_powered_on_differently_play_alike(self) -> None:
        # Arrange
        first = run_busy(0x1234)

        # Act
        others = [run_busy(seed) for seed in BUSY_SEEDS]

        # Assert
        self.assertEqual([index for index, one in enumerate(others) if one != first], [])

    def test_and_the_program_that_shows_it_makes_sound(self) -> None:
        # Arrange
        seed = 0x1234

        # Act
        rendered, _, _ = run_busy(seed)

        # Assert
        self.assertGreater(len(set(rendered)), 100)

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
