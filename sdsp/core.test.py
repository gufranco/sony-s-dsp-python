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
GAIN = 0x07
ENVX = 0x08
OUTX = 0x09
MVOLL = 0x0C
MVOLR = 0x1C
KON = 0x4C
DIR = 0x5D
FLG = 0x6C
ENDX = 0x7C

RESET_FLAGS = 0xE0
MUTE = 0x40
ECHO_WRITES_OFF = 0x20
BETWEEN_LATCH_AND_WRITE = 3
BEFORE_OUTX_WRITE = 3
WRITTEN = 0x55


def a_machine(fill: int = 0) -> Part:
    return sdsp.Chip("s-dsp", sdsp.Memory(fill=fill)).reset()


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


class ResetTest(unittest.TestCase):
    def test_a_reset_leaves_the_flag_register_where_hardware_leaves_it(self) -> None:
        # Arrange
        dsp = sdsp.Chip("s-dsp", sdsp.Memory(fill=0))

        # Act
        dsp.reset()

        # Assert
        self.assertEqual(dsp.registers[FLG], RESET_FLAGS)

    def test_a_reset_releases_every_voice(self) -> None:
        # Arrange
        dsp = sdsp.Chip("s-dsp", sdsp.Memory(fill=0))

        # Act
        dsp.reset()

        # Assert
        self.assertEqual({v.envelope_mode for v in dsp.voices}, {sdsp.ENV_RELEASE})

    def test_registers_are_not_assumed_clear_before_a_reset(self) -> None:
        # Arrange
        memory = sdsp.Memory(fill=0)

        # Act
        dsp = sdsp.Chip("s-dsp", memory)

        # Assert
        self.assertNotEqual(bytes(dsp.registers), bytes(sdsp.REGISTER_COUNT))

    def test_a_built_part_holds_the_power_on_pattern_and_nothing_a_reset_sets(self) -> None:
        # Arrange
        seed = 0x1234

        # Act
        dsp = sdsp.Chip("s-dsp", sdsp.Memory(fill=0), seed=seed)

        # Assert
        self.assertEqual(dsp.registers, sdsp.scramble(sdsp.REGISTER_COUNT, seed))

    def test_the_constructor_offers_no_way_to_arrive_reset(self) -> None:
        # Arrange
        memory = sdsp.Memory(fill=0)

        # Act
        refused = self.assertRaises(TypeError)
        with refused:
            sdsp.Chip("s-dsp", memory, reset=True)

        # Assert
        self.assertIn("reset", str(refused.exception))

    def test_only_a_call_to_reset_sets_what_a_reset_defines(self) -> None:
        # Arrange
        dsp = sdsp.Chip("s-dsp", sdsp.Memory(fill=0), seed=0x1234)

        # Act
        dsp.reset()

        # Assert
        self.assertEqual(dsp.read(FLG), RESET_FLAGS)

    def test_there_are_eight_voices(self) -> None:
        # Arrange
        memory = sdsp.Memory(fill=0)

        # Act
        dsp = sdsp.Chip("s-dsp", memory)

        # Assert
        self.assertEqual(len(dsp.voices), 8)

    def test_each_voice_knows_its_own_bit(self) -> None:
        # Arrange
        dsp = a_machine()

        # Act
        bits = [voice.bit for voice in dsp.voices]

        # Assert
        self.assertEqual(bits, [1 << n for n in range(8)])


class RegisterTest(unittest.TestCase):
    def test_a_write_reads_back(self) -> None:
        # Arrange
        dsp = a_machine()

        # Act
        dsp.write(0x00, 0x5A)

        # Assert
        self.assertEqual(dsp.read(0x00), 0x5A)

    def test_a_write_keeps_only_the_low_byte(self) -> None:
        # Arrange
        dsp = a_machine()

        # Act
        dsp.write(0x00, 0x1FF)

        # Assert
        self.assertEqual(dsp.read(0x00), 0xFF)

    def test_an_address_above_the_register_file_wraps_into_it(self) -> None:
        # Arrange
        dsp = a_machine()

        # Act
        dsp.write(0x80, 0x33)

        # Assert
        self.assertEqual(dsp.read(0x00), 0x33)

    def test_writing_key_on_arms_it_rather_than_taking_effect_at_once(self) -> None:
        # Arrange
        dsp = a_machine()

        # Act
        dsp.write(KON, 0xFF)

        # Assert
        self.assertEqual(
            {(voice.envelope_mode, voice.key_on_delay) for voice in dsp.voices},
            {(sdsp.ENV_RELEASE, 0)},
        )

    def test_and_the_armed_key_on_starts_every_voice_within_three_samples(self) -> None:
        # Arrange
        dsp = a_machine()
        dsp.write(FLG, ECHO_WRITES_OFF)
        dsp.write(KON, 0xFF)

        # Act
        dsp.render(3)

        # Assert
        self.assertEqual({voice.envelope_mode for voice in dsp.voices}, {sdsp.ENV_ATTACK})

    def test_writing_the_envelope_readback_replaces_the_value_waiting_to_be_written(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram())
        dsp.render(8)
        while dsp.phase != BETWEEN_LATCH_AND_WRITE:
            dsp.clock()
        dsp.write(ENVX, WRITTEN)

        # Act
        dsp.run(2)

        # Assert
        self.assertEqual(dsp.read(ENVX), WRITTEN)

    def test_and_writing_the_output_readback_does_the_same(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram())
        dsp.render(8)
        while dsp.phase != BEFORE_OUTX_WRITE:
            dsp.clock()
        dsp.write(OUTX, WRITTEN)

        # Act
        dsp.run(1)

        # Assert
        self.assertEqual(dsp.read(OUTX), WRITTEN)

    def test_writing_the_end_flags_clears_them(self) -> None:
        # Arrange
        dsp = a_machine()
        dsp.registers[ENDX] = 0xFF

        # Act
        dsp.write(ENDX, 0xFF)

        # Assert
        self.assertEqual(dsp.read(ENDX), 0)


class ScheduleTest(unittest.TestCase):
    def test_a_sample_takes_thirty_two_clocks(self) -> None:
        # Arrange
        schedule = sdsp.PIPELINE

        # Act
        clocks = sorted(schedule)

        # Assert
        self.assertEqual(clocks, list(range(32)))

    def test_every_clock_does_something(self) -> None:
        # Arrange
        schedule = sdsp.PIPELINE

        # Act
        idle = [clock for clock, steps in schedule.items() if not steps]

        # Assert
        self.assertEqual(idle, [])

    def test_the_phase_wraps_after_a_whole_sample(self) -> None:
        # Arrange
        dsp = a_machine()

        # Act
        dsp.run(32)

        # Assert
        self.assertEqual(dsp.phase, 0)

    def test_running_a_sample_produces_one_stereo_pair(self) -> None:
        # Arrange
        dsp = a_machine()

        # Act
        rendered = dsp.render(1)

        # Assert
        self.assertEqual(len(rendered), 2)

    def test_running_many_samples_produces_that_many_pairs(self) -> None:
        # Arrange
        dsp = a_machine()

        # Act
        rendered = dsp.render(20)

        # Assert
        self.assertEqual(len(rendered), 40)


class SilenceTest(unittest.TestCase):
    def test_a_muted_dsp_outputs_nothing(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram())
        dsp.write(FLG, MUTE)

        # Act
        rendered = dsp.render(16)

        # Assert
        self.assertEqual(set(rendered), {0})

    def test_a_reset_dsp_with_no_voices_keyed_is_silent(self) -> None:
        # Arrange
        dsp = a_machine()

        # Act
        rendered = dsp.render(16)

        # Assert
        self.assertEqual(set(rendered), {0})


class VoiceTest(unittest.TestCase):
    def test_a_keyed_voice_eventually_makes_sound(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram())

        # Act
        rendered = dsp.render(64)

        # Assert
        self.assertNotEqual(set(rendered), {0})

    def test_a_keyed_voice_is_silent_during_its_key_on_delay(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram())

        # Act
        rendered = dsp.render(3)

        # Assert
        self.assertEqual(set(rendered), {0})

    def test_a_voice_reports_its_envelope_while_it_plays(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram())

        # Act
        dsp.render(32)

        # Assert
        self.assertGreater(dsp.read(ENVX), 0)

    def test_reaching_the_end_of_a_sample_sets_the_end_flag(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram(blocks=2))

        # Act
        dsp.render(200)

        # Assert
        self.assertEqual(dsp.read(ENDX) & 0x01, 0x01)

    def test_the_same_setup_renders_the_same_audio_twice(self) -> None:
        # Arrange
        first = keyed_on(a_voice_ram()).render(48)

        # Act
        second = keyed_on(a_voice_ram()).render(48)

        # Assert
        self.assertEqual(first, second)


class WhatTheScheduleWritesTest(unittest.TestCase):
    def changing(self, samples: int = 8) -> dict[int, set[int]]:
        dsp = keyed_on(a_voice_ram())
        dsp.run(64)
        found: dict[int, set[int]] = {}
        for _ in range(samples * 32):
            before = bytes(dsp.registers)
            phase = dsp.phase
            dsp.clock()
            moved = {
                i for i, (a, b) in enumerate(zip(before, dsp.registers, strict=True)) if a != b
            }
            if moved:
                found.setdefault(phase, set()).update(moved)
        return found

    def test_the_part_writes_two_registers_of_its_own_while_a_voice_plays(self) -> None:
        # Arrange
        samples = 8

        # Act
        found = self.changing(samples)

        # Assert
        self.assertEqual(sorted(found), [3, 4])

    def test_the_first_of_them_is_the_output_the_check_names(self) -> None:
        # Arrange
        samples = 8

        # Act
        found = self.changing(samples)

        # Assert
        self.assertEqual(found[3], {OUTX})

    def test_and_the_second_is_the_envelope_the_other_check_names(self) -> None:
        # Arrange
        samples = 8

        # Act
        found = self.changing(samples)

        # Assert
        self.assertEqual(found[4], {ENVX})

    def test_a_read_is_served_without_regard_to_where_the_sample_is(self) -> None:
        # Arrange
        dsp = keyed_on(a_voice_ram())
        dsp.run(64)
        seen = {dsp.phase: dsp.read(OUTX)}

        # Act
        dsp.clock()

        # Assert
        seen[dsp.phase] = dsp.read(OUTX)
        self.assertEqual(len(seen), 2)


if __name__ == "__main__":
    unittest.main()
