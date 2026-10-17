import json
import sys
import unittest
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import Any, override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sdsp
from conformance.register_rig import Part, at

HERE = Path(__file__).resolve().parent
FACTS: dict[str, Any] = json.loads((HERE / "hardware.json").read_text())
DIVERGENCES: dict[str, Any] = json.loads((HERE / "divergences.json").read_text())

SAMPLE_RATE = 32000

ATTACK_STEPS = 64

FULL = 0x7FF

FULL_SCALE = 0x800

SETTLE = 16

LOUD = 0x7F

NOISE_CLOCK = 0x1F

COUNTER_RANGE = 30720

ECHO_WRITES_OFF = 0x20


ADSR1 = at("voice", "ADSR (1)")
ADSR2 = at("voice", "ADSR (2)")
GAIN = at("voice", "GAIN")
KON = at("global", "KON")
KOF = at("global", "KOF")
NON = at("global", "NON")
FLG = at("global", "FLG")


def _seconds(text: str) -> float:
    value, unit = text.split()
    return float(value) / (1000 if unit == "msec" else 1)


def _hertz(text: str) -> float:
    value, unit = text.split()
    return float(value) * (1000 if unit == "KHz" else 1)


def _attack_seconds(ar: int) -> float:
    period = sdsp.COUNTER_RATES[2 * ar + 1]
    steps = ATTACK_STEPS if ar < 0xF else 2
    return steps * period / SAMPLE_RATE


def _decay_ticks(target: int) -> int:
    envelope, ticks = FULL, 0
    while envelope > target:
        envelope -= 1
        envelope -= envelope >> 8
        ticks += 1
    return ticks


def _produced(rate: int) -> float:
    return 0.0 if rate == 0 else SAMPLE_RATE / sdsp.COUNTER_RATES[rate]


def _within(produced: float, printed: float) -> bool:
    return abs(produced - printed) <= max(printed * 0.03, 0.5)


def _implied_ticks() -> list[float]:
    found = []
    for value, row in enumerate(FACTS["envelope"]["decay"]):
        period = sdsp.COUNTER_RATES[2 * value + 0x10]
        found.append(_seconds(row["time"]) * SAMPLE_RATE / period)
    for row in FACTS["envelope"]["sustain"]:
        rate = int(row["sr"], 16)
        if rate:
            found.append(_seconds(row["time"]) * SAMPLE_RATE / sdsp.COUNTER_RATES[rate])
    return found


def _fraction(text: str) -> Fraction:
    whole, _, part = text.partition("-")
    return Fraction(whole) - Fraction(part) if part else Fraction(whole)


def _keyed(adsr: int, gain: int) -> Part:
    chip = sdsp.Chip("s-dsp", sdsp.Memory(fill=0)).reset()
    chip.write(FLG, ECHO_WRITES_OFF)
    chip.write(ADSR1, adsr)
    chip.write(ADSR2, 0)
    chip.write(GAIN, gain)
    chip.write(KON, 0x01)
    return chip


def _trace(chip: Part, samples: int) -> list[int]:
    found = []
    for _ in range(samples):
        chip.render(1)
        found.append(chip.voices[0].envelope)
    return found


def _then(start: int, change: tuple[int, int], samples: int) -> list[int]:
    chip = _keyed(0, start)
    chip.render(SETTLE)
    chip.write(*change)
    return _trace(chip, samples)


def _rises(trace: list[int]) -> set[int]:
    return {after - before for before, after in pairwise(trace) if after > before}


def _falls(trace: list[int]) -> set[int]:
    return {before - after for before, after in pairwise(trace) if after < before}


def _furthest_from(trace: list[int], factor: Fraction) -> Fraction:
    return max(abs(after - before * factor) for before, after in pairwise(trace) if after < before)


def _noise_clock_after(nck: int) -> int:
    chip = _keyed(0, LOUD)
    chip.write(NON, 0x01)
    chip.write(FLG, ECHO_WRITES_OFF | nck)
    chip.render(SETTLE)
    return chip.read(FLG) & NOISE_CLOCK


class DocumentTest(unittest.TestCase):
    def test_the_document_is_pinned_by_digest(self) -> None:
        # Arrange
        document = FACTS["documents"]["developmentManual"]

        # Act
        digest = document["sha256"]

        # Assert
        self.assertEqual(len(digest), 64)

    def test_what_the_manual_does_not_state_is_recorded_rather_than_filled_in(self) -> None:
        # Arrange
        facts = FACTS

        # Act
        stated = facts["notStated"]

        # Assert
        self.assertGreaterEqual(len(stated), 5)

    def test_every_table_names_the_page_it_was_read_from(self) -> None:
        # Arrange
        sections = ("registerMap", "envelope", "gain", "noiseClock")

        # Act
        missing = [name for name in sections if not FACTS[name].get("pdfPage")]

        # Assert
        self.assertEqual(missing, [])


class RegisterMapTest(unittest.TestCase):
    def test_the_voices_are_the_number_and_the_stride_the_manual_gives(self) -> None:
        # Arrange
        stride = FACTS["registerMap"]["voiceStride"]

        # Act
        voices = sdsp.Chip("s-dsp").voices

        # Assert
        self.assertEqual(
            (len(voices), {after.base - before.base for before, after in pairwise(voices)}),
            (stride["voices"], {stride["stride"]}),
        )

    def test_the_filter_is_eight_taps_starting_where_the_manual_says(self) -> None:
        # Arrange
        coefficients = [
            int(one, 16) for one in FACTS["registerMap"]["filterCoefficients"]["addresses"]
        ]

        # Act
        voices = sdsp.Chip("s-dsp").voices

        # Assert
        self.assertEqual(
            (
                len(coefficients),
                {at - voice.base for at, voice in zip(coefficients, voices, strict=True)},
            ),
            (8, {coefficients[0]}),
        )

    def test_the_map_covers_the_whole_register_file(self) -> None:
        # Arrange
        rows = FACTS["registerMap"]["global"]

        # Act
        highest = max(int(row["address"], 16) for row in rows)

        # Assert
        self.assertLess(highest, len(sdsp.Chip("s-dsp").registers))

    def test_the_registers_the_dsp_writes_to_are_named(self) -> None:
        # Arrange
        written = FACTS["registerMap"]["writtenByTheDsp"]["registers"]

        # Act
        names = sorted(written)

        # Assert
        self.assertEqual(names, ["ENDX", "ENVX", "OUTX"])


class AttackTest(unittest.TestCase):
    def test_every_printed_attack_time_is_what_this_model_takes(self) -> None:
        # Arrange
        rows = FACTS["envelope"]["attack"]

        # Act
        wrong = [
            (row["ar"], row["time"], round(_attack_seconds(int(row["ar"], 16)) * 1000, 2))
            for row in rows
            if abs(_attack_seconds(int(row["ar"], 16)) - _seconds(row["time"]))
            > max(_seconds(row["time"]) * 0.03, 0.0006)
        ]

        # Assert
        self.assertEqual(wrong, [])

    def test_that_check_covered_every_attack_rate(self) -> None:
        # Arrange
        rows = FACTS["envelope"]["attack"]

        # Act
        covered = len(rows)

        # Assert
        self.assertEqual(covered, 16)

    def test_the_slowest_attack_takes_the_four_seconds_the_manual_prints(self) -> None:
        # Arrange
        rate = 0

        # Act
        slowest = _attack_seconds(rate)

        # Assert
        self.assertAlmostEqual(slowest, 4.096, places=3)

    def test_the_fastest_attack_is_the_one_the_manual_prints_as_zero(self) -> None:
        # Arrange
        rate = 0xF

        # Act
        fastest = _attack_seconds(rate)

        # Assert
        self.assertLess(fastest, 0.001)


class NoiseClockTest(unittest.TestCase):
    def test_every_printed_noise_frequency_is_what_this_model_produces(self) -> None:
        # Arrange
        rows = FACTS["noiseClock"]["rows"]

        # Act
        wrong = [
            (row["nck"], row["frequency"], round(_produced(int(row["nck"], 16)), 1))
            for row in rows
            if not _within(_produced(int(row["nck"], 16)), _hertz(row["frequency"]))
        ]

        # Assert
        self.assertEqual(wrong, [])

    def test_that_check_covered_every_rate(self) -> None:
        # Arrange
        rows = FACTS["noiseClock"]["rows"]

        # Act
        covered = len(rows)

        # Assert
        self.assertEqual((covered, len(sdsp.COUNTER_RATES)), (32, 32))

    def test_the_tolerance_is_tight_enough_to_catch_a_table_that_moved(self) -> None:
        # Arrange
        printed = _hertz(FACTS["noiseClock"]["rows"][1]["frequency"])

        # Act
        doubled = _within(SAMPLE_RATE / (sdsp.COUNTER_RATES[1] * 2), printed)

        # Assert
        self.assertEqual(doubled, False)

    def test_the_zero_row_is_a_clock_that_never_fires(self) -> None:
        # Arrange
        rates = sdsp.COUNTER_RATES

        # Act
        never = rates[0]

        # Assert
        self.assertGreater(never, COUNTER_RANGE)

    def test_the_fastest_row_fires_every_sample(self) -> None:
        # Arrange
        rates = sdsp.COUNTER_RATES

        # Act
        fastest = rates[0x1F]

        # Assert
        self.assertEqual(fastest, 1)


class ExponentialTest(unittest.TestCase):
    def test_every_printed_figure_implies_the_same_length_of_fall(self) -> None:
        # Arrange
        implied = _implied_ticks()

        # Act
        spread = (max(implied) - min(implied)) / (sum(implied) / len(implied))

        # Assert
        self.assertLess(spread, 0.05)

    def test_that_check_covered_both_columns_in_full(self) -> None:
        # Arrange
        implied = _implied_ticks()

        # Act
        covered = len(implied)

        # Assert
        self.assertEqual(covered, 8 + 31)

    def test_the_recovered_endpoint_is_recorded_rather_than_built_in(self) -> None:
        # Arrange
        entries = DIVERGENCES["divergences"]

        # Act
        entry = next(item for item in entries if item["id"] == "unstated-decay-endpoint")

        # Assert
        self.assertIn("590", entry["referenceDoes"])

    def test_the_model_reaches_the_first_sustain_level_where_the_manual_puts_it(self) -> None:
        # Arrange
        ratio = FACTS["envelope"]["sustainLevel"][0]["ratio"]

        # Act
        ticks = _decay_ticks((FULL + 1) // 8 - 1)

        # Assert
        self.assertEqual((ratio, ticks), ("1/8", 440))

    def test_a_slower_rate_always_takes_longer(self) -> None:
        # Arrange
        rates = range(1, 32)

        # Act
        periods = [sdsp.COUNTER_RATES[rate] for rate in rates]

        # Assert
        self.assertEqual(periods, sorted(periods, reverse=True))


class DivergenceTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.entries: list[dict[str, Any]] = DIVERGENCES["divergences"]

    def test_each_entry_says_which_source_the_package_follows(self) -> None:
        # Arrange
        allowed = {"document", "reference", "neither"}

        # Act
        followed = {entry["packageFollows"] for entry in self.entries}

        # Assert
        self.assertEqual(followed - allowed, set())

    def test_each_entry_says_what_would_settle_it(self) -> None:
        # Arrange
        entries = self.entries

        # Act
        missing = [entry["id"] for entry in entries if not entry.get("wouldSettleIt")]

        # Assert
        self.assertEqual(missing, [])

    def test_the_reference_being_an_emulator_is_recorded_as_a_limit(self) -> None:
        # Arrange
        entries = self.entries

        # Act
        entry = next(item for item in entries if item["id"] == "the-audio-rests-on-an-emulator")

        # Assert
        self.assertEqual(entry["severity"], "high")

    def test_the_gaussian_kernel_is_recorded_as_undocumented(self) -> None:
        # Arrange
        entries = self.entries

        # Act
        named = {entry["id"] for entry in entries}

        # Assert
        self.assertIn("gaussian-kernel-is-undocumented", named)


class PrintedStepTest(unittest.TestCase):
    def test_an_attack_climbs_by_the_printed_step(self) -> None:
        # Arrange
        step = _fraction(FACTS["envelope"]["steps"]["attackStep"]) * FULL_SCALE
        chip = _keyed(0x8E, 0)

        # Act
        found = _trace(chip, 40)

        # Assert
        self.assertEqual(_rises(found), {step})

    def test_a_decay_falls_by_the_printed_factor(self) -> None:
        # Arrange
        factor = _fraction(FACTS["envelope"]["steps"]["decayFactor"])
        chip = _keyed(0xFF, 0)
        chip.render(SETTLE)

        # Act
        found = _trace(chip, 200)

        # Assert
        self.assertEqual((len(_falls(found)) > 1, _furthest_from(found, factor) < 1), (True, True))

    def test_a_key_off_falls_by_the_printed_step(self) -> None:
        # Arrange
        step = _fraction(FACTS["envelope"]["steps"]["keyOffStep"]) * FULL_SCALE

        # Act
        found = _then(LOUD, (KOF, 0x01), 300)

        # Assert
        self.assertEqual(_falls(found), {step})

    def test_gain_mode_steps_by_the_same_printed_values(self) -> None:
        # Arrange
        steps = FACTS["envelope"]["steps"]
        step = _fraction(steps["attackStep"]) * FULL_SCALE
        factor = _fraction(steps["decayFactor"])

        # Act
        found = [
            _then(0x00, (GAIN, 0xDF), 40),
            _then(LOUD, (GAIN, 0x9F), 40),
            _then(LOUD, (GAIN, 0xBF), 200),
        ]

        # Assert
        self.assertEqual(
            (_rises(found[0]), _falls(found[1]), _furthest_from(found[2], factor) < 1),
            ({step}, {step}, True),
        )


class NoiseClockWriteTest(unittest.TestCase):
    def test_only_the_cpu_writes_the_noise_clock(self) -> None:
        # Arrange
        rows = [int(row["nck"], 16) for row in FACTS["noiseClock"]["rows"]]

        # Act
        found = [_noise_clock_after(nck) for nck in rows]

        # Assert
        self.assertEqual(found, rows)


if __name__ == "__main__":
    unittest.main(verbosity=1)
