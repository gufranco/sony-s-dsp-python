import random
import struct
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sdsp
from conformance.register_rig import Part

BRR_BLOCK_BYTES = 9

VOLL = 0x00
PITCHL = 0x02
PITCHH = 0x03
ADSR1 = 0x05
ADSR2 = 0x06
GAIN = 0x07
OUTX = 0x09
MVOLL = 0x0C
MVOLR = 0x1C
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
FULL_NEGATIVE_OUTX = 0x81


def a_voice_ram(
    rng_seed: int = 7, blocks: int = 16, at: int = 0x1000, directory: int = 0x0200
) -> sdsp.Memory:
    rng = random.Random(rng_seed)
    memory = sdsp.Memory(fill=0)
    for block in range(blocks):
        base = at + block * BRR_BLOCK_BYTES
        memory.write8(base, 12 << 4)
        for offset in range(8):
            memory.write8(base + 1 + offset, rng.randrange(256))
    last = at + (blocks - 1) * BRR_BLOCK_BYTES
    memory.write8(last, memory.read8(last) | 0x01)
    for index, value in enumerate(struct.pack("<HH", at, at)):
        memory.write8(directory + index, value)
    return memory


def keyed_on(memory: sdsp.Memory, directory: int = 0x02, **options: Any) -> Part:
    dsp = sdsp.Chip("s-dsp", memory, **options).reset()
    dsp.write(DIR, directory)
    dsp.write(MVOLL, 0x7F)
    dsp.write(MVOLR, 0x7F)
    dsp.write(VOLL, 0x7F)
    dsp.write(VOLL + 1, 0x7F)
    dsp.write(PITCHL, 0x00)
    dsp.write(PITCHH, 0x10)
    dsp.write(GAIN, 0x7F)
    dsp.write(FLG, ECHO_WRITES_OFF)
    dsp.write(KON, 0x01)
    return dsp


def outx_each_sample(dsp: Part, samples: int) -> list[int]:
    found = []
    for _ in range(samples):
        dsp.render(1)
        found.append(dsp.read(OUTX))
    return found


def echo_region(memory: sdsp.Memory) -> set[int]:
    return {memory.read8(address) for address in range(0x4000, 0x4100)}


class EnvelopeTest(unittest.TestCase):
    def test_a_released_voice_falls_to_nothing(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram())
        dsp.render(32)
        dsp.write(KOFF, 0x01)

        # Act
        dsp.render(400)

        # Assert
        self.assertEqual(dsp.voices[0].envelope, 0)

    def test_direct_gain_holds_the_level_it_was_given(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram())

        # Act
        dsp.render(64)

        # Assert
        self.assertEqual(dsp.voices[0].envelope, 0x7F * 0x10)

    def test_linear_decrease_gain_falls_by_a_fixed_step(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram())
        dsp.render(16)
        raised = dsp.voices[0].envelope
        dsp.write(GAIN, 0x9F)

        # Act
        dsp.render(8)

        # Assert
        self.assertLess(dsp.voices[0].envelope, raised)

    def test_exponential_decrease_gain_falls_away(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram())
        dsp.render(16)
        raised = dsp.voices[0].envelope
        dsp.write(GAIN, 0xBF)

        # Act
        dsp.render(8)

        # Assert
        self.assertLess(dsp.voices[0].envelope, raised)

    def test_linear_increase_gain_climbs(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram())
        dsp.write(GAIN, 0xDF)

        # Act
        dsp.render(40)

        # Assert
        self.assertGreater(dsp.voices[0].envelope, 0)

    def test_bent_increase_gain_climbs_then_slows(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram())
        dsp.write(GAIN, 0xFF)

        # Act
        dsp.render(200)

        # Assert
        self.assertGreater(dsp.voices[0].hidden_envelope, 0x600)

    def test_an_attack_climbs_from_nothing(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram())
        dsp.write(ADSR1, 0x8F)
        dsp.write(ADSR2, 0xE0)

        # Act
        dsp.render(40)

        # Assert
        self.assertGreater(dsp.voices[0].envelope, 0)


class NoiseTest(unittest.TestCase):
    def test_the_noise_generator_starts_where_the_reset_puts_it(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram())
        dsp.write(NON, 0x01)

        # Act
        found = outx_each_sample(dsp, 16)[8:]

        # Assert
        self.assertEqual(set(found), {FULL_NEGATIVE_OUTX})

    def test_the_noise_generator_moves_when_it_is_clocked(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram())
        dsp.write(NON, 0x01)
        dsp.write(FLG, ECHO_WRITES_OFF | NOISE_EVERY_SAMPLE)

        # Act
        found = outx_each_sample(dsp, 64)[8:]

        # Assert
        self.assertGreater(len(set(found)), 8)

    def test_a_voice_can_be_switched_to_noise(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram())
        dsp.write(NON, 0x01)
        dsp.write(FLG, 0x2F)

        # Act
        rendered = dsp.render(64)

        # Assert
        self.assertNotEqual(set(rendered), {0})


class EchoTest(unittest.TestCase):
    def test_echo_writes_are_suppressed_while_the_flag_says_so(self) -> None:
        # Arrange
        memory = a_voice_ram()
        dsp = keyed_on(memory)
        dsp.write(ESA, 0x40)
        dsp.write(EDL, 0x01)

        # Act
        dsp.render(64)

        # Assert
        self.assertEqual(echo_region(memory), {0})

    def test_echo_writes_reach_memory_once_it_is_enabled(self) -> None:
        # Arrange
        memory = a_voice_ram()
        dsp = keyed_on(memory)
        dsp.write(ESA, 0x40)
        dsp.write(EDL, 0x01)
        dsp.write(EON, 0x01)
        dsp.write(FLG, 0x00)

        # Act
        dsp.render(200)

        # Assert
        self.assertNotEqual(echo_region(memory), {0})


class SuppliedKernelTest(unittest.TestCase):
    def a_part(self, **options: Any) -> Part:
        return sdsp.Chip("s-dsp", sdsp.Memory(), **options)

    def test_a_part_built_with_no_kernel_uses_the_published_one(self) -> None:
        # Arrange
        options: dict[str, Any] = {}

        # Act
        part = self.a_part(**options)

        # Assert
        self.assertIs(part.gaussian, sdsp.GAUSSIAN)

    def test_a_supplied_kernel_reaches_the_part(self) -> None:
        # Arrange
        supplied = list(sdsp.GAUSSIAN)

        # Act
        found = self.a_part(gaussian=supplied).gaussian

        # Assert
        self.assertEqual(found, sdsp.GAUSSIAN)

    def test_two_parts_do_not_share_one_kernel(self) -> None:
        # Arrange
        first = self.a_part(gaussian=list(sdsp.GAUSSIAN))

        # Act
        second = self.a_part()

        # Assert
        self.assertIsNot(first.gaussian, second.gaussian)

    def test_supplying_one_leaves_the_published_table_alone(self) -> None:
        # Arrange
        held = tuple(sdsp.GAUSSIAN)

        # Act
        self.a_part(gaussian=[*sdsp.GAUSSIAN[:-1], sdsp.GAUSSIAN[-1] + 1])

        # Assert
        self.assertEqual(sdsp.GAUSSIAN, held)

    def test_a_kernel_that_cannot_be_the_parts_is_refused_at_construction(self) -> None:
        # Arrange
        flat = [0] * 512

        # Act
        refused = self.assertRaises(sdsp.NotAKernel)
        with refused:
            self.a_part(gaussian=flat)

        # Assert
        self.assertIn("sum to", str(refused.exception))

    def test_and_the_part_is_not_built(self) -> None:
        # Arrange
        short = sdsp.GAUSSIAN[:8]

        # Act
        refused = self.assertRaises(sdsp.NotAKernel)
        with refused:
            self.a_part(gaussian=short)

        # Assert
        self.assertIn("512", str(refused.exception))

    def test_a_different_kernel_changes_what_a_voice_renders(self) -> None:
        # Arrange
        published = keyed_on(a_voice_ram()).render(48)
        bent = [
            min(0x7FFF, value + (1 if 256 <= at < 512 else -1))
            for at, value in enumerate(sdsp.GAUSSIAN)
        ]

        # Act
        supplied = keyed_on(a_voice_ram(), gaussian=bent).render(48)

        # Assert
        self.assertNotEqual(supplied, published)


if __name__ == "__main__":
    unittest.main()
