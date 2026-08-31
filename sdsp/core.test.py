import struct
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sdsp import core, tables
from sdsp.errors import NotAKernel
from sdsp.memory import Memory


def a_machine(fill: int = 0) -> Any:
    return core.Chip(Memory(fill=fill))


def a_voice_ram(
    rng_seed: int = 7, blocks: int = 16, at: int = 0x1000, directory: int = 0x0200
) -> Any:
    import random

    rng = random.Random(rng_seed)
    memory = Memory(fill=0)
    for block in range(blocks):
        base = at + block * core.BRR_BLOCK_BYTES
        memory.write8(base, 12 << 4)
        for offset in range(8):
            memory.write8(base + 1 + offset, rng.randrange(256))
    last = at + (blocks - 1) * core.BRR_BLOCK_BYTES
    memory.write8(last, memory.read8(last) | 0x01)
    for index, value in enumerate(struct.pack("<HH", at, at)):
        memory.write8(directory + index, value)
    return memory


def keyed_on(memory: Any, directory: int = 0x02) -> Any:
    dsp = core.Chip(memory)
    dsp.write(core.REG_DIR, directory)
    dsp.write(core.REG_MVOLL, 0x7F)
    dsp.write(core.REG_MVOLL + 0x10, 0x7F)
    dsp.write(core.V_VOLL, 0x7F)
    dsp.write(core.V_VOLL + 1, 0x7F)
    dsp.write(core.V_PITCHL, 0x00)
    dsp.write(core.V_PITCHH, 0x10)
    dsp.write(core.V_GAIN, 0x7F)
    dsp.write(core.REG_FLG, 0x20)
    dsp.write(core.REG_KON, 0x01)
    return dsp


class ResetTest(unittest.TestCase):
    def test_a_reset_leaves_the_flag_register_where_hardware_leaves_it(self) -> None:
        self.assertEqual(a_machine().registers[core.REG_FLG], 0xE0)

    def test_a_reset_releases_every_voice(self) -> None:
        dsp = a_machine()

        self.assertTrue(all(v.envelope_mode == core.ENV_RELEASE for v in dsp.voices))

    def test_registers_are_not_assumed_clear_before_a_reset(self) -> None:
        dsp = core.Chip(Memory(fill=0), reset=False)

        self.assertNotEqual(bytes(dsp.registers), bytes(core.REGISTER_COUNT))

    def test_there_are_eight_voices(self) -> None:
        self.assertEqual(len(a_machine().voices), core.VOICE_COUNT)

    def test_each_voice_knows_its_own_bit(self) -> None:
        self.assertEqual([v.bit for v in a_machine().voices], [1 << n for n in range(8)])


class RegisterTest(unittest.TestCase):
    def test_a_write_reads_back(self) -> None:
        dsp = a_machine()

        dsp.write(0x00, 0x5A)

        self.assertEqual(dsp.read(0x00), 0x5A)

    def test_a_write_keeps_only_the_low_byte(self) -> None:
        dsp = a_machine()

        dsp.write(0x00, 0x1FF)

        self.assertEqual(dsp.read(0x00), 0xFF)

    def test_an_address_above_the_register_file_wraps_into_it(self) -> None:
        dsp = a_machine()

        dsp.write(0x80, 0x33)

        self.assertEqual(dsp.read(0x00), 0x33)

    def test_writing_key_on_arms_it_rather_than_taking_effect_at_once(self) -> None:
        dsp = a_machine()

        dsp.write(core.REG_KON, 0xFF)

        self.assertEqual(dsp.new_kon, 0xFF)
        self.assertEqual(dsp.kon, 0)

    def test_writing_the_end_flags_clears_them(self) -> None:
        dsp = a_machine()
        dsp.registers[core.REG_ENDX] = 0xFF

        dsp.write(core.REG_ENDX, 0xFF)

        self.assertEqual(dsp.read(core.REG_ENDX), 0)


class ScheduleTest(unittest.TestCase):
    def test_a_sample_takes_thirty_two_clocks(self) -> None:
        self.assertEqual(len(core.SCHEDULE), 32)

    def test_every_clock_does_something(self) -> None:
        self.assertTrue(all(len(steps) for steps in core.SCHEDULE))

    def test_the_phase_wraps_after_a_whole_sample(self) -> None:
        dsp = a_machine()

        dsp.run(32)

        self.assertEqual(dsp.phase, 0)

    def test_running_a_sample_produces_one_stereo_pair(self) -> None:
        dsp = a_machine()

        self.assertEqual(len(dsp.render(1)), 2)

    def test_running_many_samples_produces_that_many_pairs(self) -> None:
        self.assertEqual(len(a_machine().render(20)), 40)


class SilenceTest(unittest.TestCase):
    def test_a_muted_dsp_outputs_nothing(self) -> None:
        dsp = a_machine()
        dsp.write(core.REG_FLG, core.FLG_MUTE)

        self.assertEqual(set(dsp.render(16)), {0})

    def test_a_reset_dsp_with_no_voices_keyed_is_silent(self) -> None:
        self.assertEqual(set(a_machine().render(16)), {0})


class VoiceTest(unittest.TestCase):
    def test_a_keyed_voice_eventually_makes_sound(self) -> None:
        dsp = keyed_on(a_voice_ram())

        rendered = dsp.render(64)

        self.assertTrue(any(value != 0 for value in rendered))

    def test_a_keyed_voice_is_silent_during_its_key_on_delay(self) -> None:
        dsp = keyed_on(a_voice_ram())

        rendered = dsp.render(3)

        self.assertEqual(set(rendered), {0})

    def test_a_voice_reports_its_envelope_while_it_plays(self) -> None:
        dsp = keyed_on(a_voice_ram())

        dsp.render(32)

        self.assertGreater(dsp.read(core.V_ENVX), 0)

    def test_reaching_the_end_of_a_sample_sets_the_end_flag(self) -> None:
        dsp = keyed_on(a_voice_ram(blocks=2))

        dsp.render(200)

        self.assertTrue(dsp.read(core.REG_ENDX) & 0x01)

    def test_the_same_setup_renders_the_same_audio_twice(self) -> None:
        first = keyed_on(a_voice_ram()).render(48)
        second = keyed_on(a_voice_ram()).render(48)

        self.assertEqual(first, second)


class EnvelopeTest(unittest.TestCase):
    def test_a_released_voice_falls_to_nothing(self) -> None:
        dsp = keyed_on(a_voice_ram())
        dsp.render(32)

        dsp.write(core.REG_KOFF, 0x01)
        dsp.render(400)

        self.assertEqual(dsp.voices[0].envelope, 0)

    def test_direct_gain_holds_the_level_it_was_given(self) -> None:
        dsp = keyed_on(a_voice_ram())

        dsp.render(64)

        self.assertEqual(dsp.voices[0].envelope, 0x7F * 0x10)

    def test_linear_decrease_gain_falls_by_a_fixed_step(self) -> None:
        dsp = keyed_on(a_voice_ram())
        dsp.render(16)
        raised = dsp.voices[0].envelope

        dsp.write(core.V_GAIN, 0x9F)
        dsp.render(8)

        self.assertLess(dsp.voices[0].envelope, raised)

    def test_exponential_decrease_gain_falls_away(self) -> None:
        dsp = keyed_on(a_voice_ram())
        dsp.render(16)
        raised = dsp.voices[0].envelope

        dsp.write(core.V_GAIN, 0xBF)
        dsp.render(8)

        self.assertLess(dsp.voices[0].envelope, raised)

    def test_linear_increase_gain_climbs(self) -> None:
        dsp = keyed_on(a_voice_ram())
        dsp.write(core.V_GAIN, 0xDF)

        dsp.render(40)

        self.assertGreater(dsp.voices[0].envelope, 0)

    def test_bent_increase_gain_climbs_then_slows(self) -> None:
        dsp = keyed_on(a_voice_ram())
        dsp.write(core.V_GAIN, 0xFF)

        dsp.render(200)

        self.assertGreater(dsp.voices[0].hidden_envelope, 0x600)

    def test_an_attack_climbs_from_nothing(self) -> None:
        dsp = keyed_on(a_voice_ram())
        dsp.write(core.V_ADSR0, 0x8F)
        dsp.write(core.V_ADSR1, 0xE0)

        dsp.render(40)

        self.assertGreater(dsp.voices[0].envelope, 0)


class NoiseTest(unittest.TestCase):
    def test_the_noise_register_starts_where_hardware_starts_it(self) -> None:
        self.assertEqual(a_machine().noise, 0x4000)

    def test_the_noise_generator_moves_when_it_is_clocked(self) -> None:
        dsp = a_machine()
        dsp.write(core.REG_FLG, 0x3F)

        dsp.render(64)

        self.assertNotEqual(dsp.noise, 0x4000)

    def test_a_voice_can_be_switched_to_noise(self) -> None:
        dsp = keyed_on(a_voice_ram())
        dsp.write(core.REG_NON, 0x01)
        dsp.write(core.REG_FLG, 0x2F)

        self.assertTrue(any(value != 0 for value in dsp.render(64)))


class EchoTest(unittest.TestCase):
    def test_echo_writes_are_suppressed_while_the_flag_says_so(self) -> None:
        memory = a_voice_ram()
        dsp = keyed_on(memory)
        dsp.write(core.REG_ESA, 0x40)
        dsp.write(core.REG_EDL, 0x01)

        dsp.render(64)

        self.assertEqual(set(memory.data[0x4000:0x4100]), {0})

    def test_echo_writes_reach_memory_once_it_is_enabled(self) -> None:
        memory = a_voice_ram()
        dsp = keyed_on(memory)
        dsp.write(core.REG_ESA, 0x40)
        dsp.write(core.REG_EDL, 0x01)
        dsp.write(core.REG_EON, 0x01)
        dsp.write(core.REG_FLG, 0x00)

        dsp.render(200)

        self.assertNotEqual(set(memory.data[0x4000:0x4100]), {0})


class HelperTest(unittest.TestCase):
    def test_clamping_holds_a_word_that_already_fits(self) -> None:
        self.assertEqual(core._clamp16(1234), 1234)

    def test_clamping_stops_at_the_top_of_the_range(self) -> None:
        self.assertEqual(core._clamp16(0x9000), 0x7FFF)

    def test_clamping_stops_at_the_bottom_of_the_range(self) -> None:
        self.assertEqual(core._clamp16(-0x9000), -0x8000)

    def test_a_byte_reads_as_signed(self) -> None:
        self.assertEqual([core._signed8(0x7F), core._signed8(0x80)], [127, -128])

    def test_a_word_reads_as_signed(self) -> None:
        self.assertEqual([core._signed16(0x7FFF), core._signed16(0x8000)], [32767, -32768])


class SuppliedKernelTest(unittest.TestCase):
    """That a caller's kernel reaches one part and no other.

    Held on the instance rather than rebound on the module, so two parts in one
    process carry different tables and neither can change what the other reads.
    A module global would make the last constructor win for everybody.
    """

    def a_part(self, **options: Any) -> Any:
        return core.Chip(Memory(), **options)

    def test_a_part_built_with_no_kernel_uses_the_published_one(self) -> None:
        self.assertIs(self.a_part().gaussian, tables.GAUSSIAN)

    def test_a_supplied_kernel_reaches_the_part(self) -> None:
        supplied = list(tables.GAUSSIAN)

        found = self.a_part(gaussian=supplied).gaussian

        self.assertEqual(found, tables.GAUSSIAN)

    def test_two_parts_do_not_share_one_kernel(self) -> None:
        first = self.a_part(gaussian=list(tables.GAUSSIAN))

        second = self.a_part()

        self.assertIsNot(first.gaussian, second.gaussian)

    def test_supplying_one_leaves_the_published_table_alone(self) -> None:
        held = tuple(tables.GAUSSIAN)

        self.a_part(gaussian=list(tables.GAUSSIAN))

        self.assertEqual(tables.GAUSSIAN, held)

    def test_a_kernel_that_cannot_be_the_parts_is_refused_at_construction(self) -> None:
        with self.assertRaises(NotAKernel):
            self.a_part(gaussian=[0] * 512)

    def test_and_the_part_is_not_built(self) -> None:
        with self.assertRaises(NotAKernel):
            self.a_part(gaussian=tables.GAUSSIAN[:8])

    def test_a_different_kernel_changes_what_a_voice_interpolates(self) -> None:
        flat = self.a_part()
        flat.voices[0].buffer = [0, 0x2000, 0x4000, 0x2000] + [0] * 8
        flat.voices[0].buffer_position = 0
        flat.voices[0].interpolation = 0x0800

        with_published = flat._interpolate(flat.voices[0])
        flat.gaussian = tables.check_kernel(
            [
                min(0x7FFF, value + (1 if 256 <= at < 512 else -1))
                for at, value in enumerate(tables.GAUSSIAN)
            ]
        )
        with_supplied = flat._interpolate(flat.voices[0])

        self.assertNotEqual(with_published, with_supplied)


class WhatTheScheduleWritesTest(unittest.TestCase):
    """Which registers the part writes on its own, and at which phase.

    This is the evidence behind one entry in the record. Two of Shay Green's
    timing checks disagree with this model, `V8 outx` and `V9 envx`, and they are
    the only two that sample a register the part writes rather than one the
    console wrote. A register read is served straight out of the file with no
    relation to where in the sample the part is, and a phase runs whole, so
    nothing here orders the part's own write against a console read inside one
    phase.

    A test rather than a sentence, because the reasoning stops holding the moment
    a fourth register starts being written by the schedule.
    """

    def changing(self, samples: int = 8) -> dict[int, set[int]]:
        dsp = keyed_on(a_voice_ram())
        for _ in range(64):
            dsp.clock()
        found: dict[int, set[int]] = {}
        for _ in range(samples * 32):
            before = bytes(dsp.registers)
            phase = dsp.phase
            dsp.clock()
            after = bytes(dsp.registers)
            moved = {i for i, (a, b) in enumerate(zip(before, after, strict=True)) if a != b}
            if moved:
                found.setdefault(phase, set()).update(moved)
        return found

    def test_the_part_writes_two_registers_of_its_own_while_a_voice_plays(self) -> None:
        found = self.changing()

        self.assertEqual(sorted(found), [3, 4])

    def test_the_first_of_them_is_the_output_the_check_names(self) -> None:
        self.assertEqual(self.changing()[3], {core.V_OUTX})

    def test_and_the_second_is_the_envelope_the_other_check_names(self) -> None:
        self.assertEqual(self.changing()[4], {core.V_ENVX})

    def test_a_read_is_served_without_regard_to_where_the_sample_is(self) -> None:
        dsp = keyed_on(a_voice_ram())
        for _ in range(64):
            dsp.clock()

        seen = {dsp.phase: dsp.read(core.V_OUTX)}
        dsp.clock()
        seen[dsp.phase] = dsp.read(core.V_OUTX)

        self.assertEqual(len(seen), 2)


if __name__ == "__main__":
    unittest.main()
