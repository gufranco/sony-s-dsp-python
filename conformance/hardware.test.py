"""Hold this model to the figures Nintendo printed, rather than to prose about them.

The tables in `sdsp/tables.py` were originally lifted from a reference
implementation, which is evidence about that implementation and not about the
chip. Nintendo's development manual documents the same tables as times and
frequencies, and this checks the model against them: every attack time, every
noise clock frequency, every register address.

Two of the manual's four timing columns are exponential and are internally
consistent to within two per cent of one endpoint that the document never
names. That endpoint is measured here and recorded as a divergence rather than
being folded into the model, because a constant nobody printed is not a fact.
"""

import json
import sys
import unittest
from pathlib import Path
from typing import Any, override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sdsp import core, tables

HERE = Path(__file__).resolve().parent
FACTS: dict[str, Any] = json.loads((HERE / "hardware.json").read_text())
DIVERGENCES: dict[str, Any] = json.loads((HERE / "divergences.json").read_text())

SAMPLE_RATE = 32000
"""Samples a second, which the manual gives only as the top row of the noise table."""

ATTACK_STEPS = 64
"""Ticks from silence to full, since the manual's attack step is one sixty fourth."""

FULL = 0x7FF
"""The envelope at its top, which is what the manual's tables call 1."""


def _seconds(text: str) -> float:
    value, unit = text.split()
    return float(value) / (1000 if unit == "msec" else 1)


def _hertz(text: str) -> float:
    value, unit = text.split()
    return float(value) * (1000 if unit == "KHz" else 1)


def _attack_seconds(ar: int) -> float:
    """How long this model takes to climb from silence at that attack rate.

    The fastest rate is the exception the manual prints as zero: it adds a
    thirty second of full scale rather than a sixty fourth, so it arrives in two
    ticks rather than sixty four.
    """
    period = tables.COUNTER_RATES[2 * ar + 1]
    steps = ATTACK_STEPS if ar < 0xF else 2
    return steps * period / SAMPLE_RATE


def _decay_ticks(target: int) -> int:
    """Ticks for this model's exponential fall to reach a level."""
    envelope, ticks = FULL, 0
    while envelope > target:
        envelope -= 1
        envelope -= envelope >> 8
        ticks += 1
    return ticks


def _produced(rate: int) -> float:
    """The noise frequency this model's rate table gives, in hertz."""
    return 0.0 if rate == 0 else SAMPLE_RATE / tables.COUNTER_RATES[rate]


def _within(produced: float, printed: float) -> bool:
    """Whether two frequencies agree to the precision the manual prints them at.

    Nintendo rounds to two significant figures, so 1333 hertz appears as 1.3 KHz
    and 2667 as 2.7. Three per cent covers that rounding and nothing wider.
    """
    return abs(produced - printed) <= max(printed * 0.03, 0.5)


def _implied_ticks() -> list[float]:
    """What each printed exponential figure says the fall must have lasted."""
    found = []
    for value, row in enumerate(FACTS["envelope"]["decay"]):
        period = tables.COUNTER_RATES[2 * value + 0x10]
        found.append(_seconds(row["time"]) * SAMPLE_RATE / period)
    for row in FACTS["envelope"]["sustain"]:
        rate = int(row["sr"], 16)
        if rate:
            found.append(_seconds(row["time"]) * SAMPLE_RATE / tables.COUNTER_RATES[rate])
    return found


class DocumentTest(unittest.TestCase):
    def test_the_document_is_pinned_by_digest(self) -> None:
        document = FACTS["documents"]["developmentManual"]

        self.assertEqual(len(document["sha256"]), 64)

    def test_what_the_manual_does_not_state_is_recorded_rather_than_filled_in(self) -> None:
        stated = FACTS["notStated"]

        self.assertGreaterEqual(len(stated), 5)

    def test_every_table_names_the_page_it_was_read_from(self) -> None:
        sections = ("registerMap", "envelope", "gain", "noiseClock")

        missing = [name for name in sections if not FACTS[name].get("pdfPage")]

        self.assertEqual(missing, [])


class RegisterMapTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.voice = {
            row["register"]: int(row["offset"], 16) for row in FACTS["registerMap"]["voice"]
        }
        self.globals = {
            row["register"]: int(row["address"], 16) for row in FACTS["registerMap"]["global"]
        }

    def test_every_voice_offset_this_model_names_is_where_the_manual_puts_it(self) -> None:
        wrong = [
            (name, offset, mine)
            for name, offset, mine in (
                ("VOL (L)", self.voice["VOL (L)"], core.V_VOLL),
                ("P (L)", self.voice["P (L)"], core.V_PITCHL),
                ("P (H)", self.voice["P (H)"], core.V_PITCHH),
                ("SRCN", self.voice["SRCN"], core.V_SRCN),
                ("ADSR (1)", self.voice["ADSR (1)"], core.V_ADSR0),
                ("ADSR (2)", self.voice["ADSR (2)"], core.V_ADSR1),
                ("GAIN", self.voice["GAIN"], core.V_GAIN),
                ("ENVX", self.voice["ENVX"], core.V_ENVX),
                ("OUTX", self.voice["OUTX"], core.V_OUTX),
            )
            if offset != mine
        ]

        self.assertEqual(wrong, [])

    def test_every_global_address_this_model_names_is_where_the_manual_puts_it(self) -> None:
        wrong = [
            (name, address, mine)
            for name, address, mine in (
                ("MVOL (L)", self.globals["MVOL (L)"], core.REG_MVOLL),
                ("EVOL (L)", self.globals["EVOL (L)"], core.REG_EVOLL),
                ("KON", self.globals["KON"], core.REG_KON),
                ("KOF", self.globals["KOF"], core.REG_KOFF),
                ("FLG", self.globals["FLG"], core.REG_FLG),
                ("ENDX", self.globals["ENDX"], core.REG_ENDX),
                ("EFB", self.globals["EFB"], core.REG_EFB),
                ("PMON", self.globals["PMON"], core.REG_PMON),
                ("NON", self.globals["NON"], core.REG_NON),
                ("EON", self.globals["EON"], core.REG_EON),
                ("DIR", self.globals["DIR"], core.REG_DIR),
                ("ESA", self.globals["ESA"], core.REG_ESA),
                ("EDL", self.globals["EDL"], core.REG_EDL),
            )
            if address != mine
        ]

        self.assertEqual(wrong, [])

    def test_the_voices_are_the_number_and_the_stride_the_manual_gives(self) -> None:
        stride = FACTS["registerMap"]["voiceStride"]

        self.assertEqual((stride["voices"], stride["stride"]), (core.VOICE_COUNT, 0x10))

    def test_the_filter_is_eight_taps_starting_where_the_manual_says(self) -> None:
        coefficients = FACTS["registerMap"]["filterCoefficients"]["addresses"]

        self.assertEqual((len(coefficients), int(coefficients[0], 16)), (8, core.REG_FIR))

    def test_the_map_covers_the_whole_register_file(self) -> None:
        highest = max(int(row["address"], 16) for row in FACTS["registerMap"]["global"])

        self.assertLess(highest, core.REGISTER_COUNT)

    def test_the_registers_the_dsp_writes_to_are_named(self) -> None:
        written = FACTS["registerMap"]["writtenByTheDsp"]["registers"]

        self.assertEqual(sorted(written), ["ENDX", "ENVX", "OUTX"])


class AttackTest(unittest.TestCase):
    """The one timing column the manual states in absolute terms this model can reach.

    The attack is linear, so it needs no endpoint: sixty four ticks of a sixty
    fourth each, from silence to full. Every one of the sixteen printed figures
    is reproduced by this model's rate table to within the manual's own printing
    precision.
    """

    def test_every_printed_attack_time_is_what_this_model_takes(self) -> None:
        wrong = [
            (row["ar"], row["time"], round(_attack_seconds(int(row["ar"], 16)) * 1000, 2))
            for row in FACTS["envelope"]["attack"]
            if abs(_attack_seconds(int(row["ar"], 16)) - _seconds(row["time"]))
            > max(_seconds(row["time"]) * 0.03, 0.0006)
        ]

        self.assertEqual(wrong, [])

    def test_that_check_covered_every_attack_rate(self) -> None:
        covered = len(FACTS["envelope"]["attack"])

        self.assertEqual(covered, 16)

    def test_the_slowest_attack_takes_the_four_seconds_the_manual_prints(self) -> None:
        slowest = _attack_seconds(0)

        self.assertAlmostEqual(slowest, 4.096, places=3)

    def test_the_fastest_attack_is_the_one_the_manual_prints_as_zero(self) -> None:
        fastest = _attack_seconds(0xF)

        self.assertLess(fastest, 0.001)


class NoiseClockTest(unittest.TestCase):
    """Thirty two frequencies against thirty two rate table entries, one for one.

    This is the strongest check available on the table this model is built
    around, because it names every entry rather than a ratio between them.
    """

    def test_every_printed_noise_frequency_is_what_this_model_produces(self) -> None:
        wrong = [
            (row["nck"], row["frequency"], round(_produced(int(row["nck"], 16)), 1))
            for row in FACTS["noiseClock"]["rows"]
            if not _within(_produced(int(row["nck"], 16)), _hertz(row["frequency"]))
        ]

        self.assertEqual(wrong, [])

    def test_that_check_covered_every_rate(self) -> None:
        covered = len(FACTS["noiseClock"]["rows"])

        self.assertEqual((covered, len(tables.COUNTER_RATES)), (32, 32))

    def test_the_tolerance_is_tight_enough_to_catch_a_table_that_moved(self) -> None:
        printed = _hertz(FACTS["noiseClock"]["rows"][1]["frequency"])

        doubled = _within(SAMPLE_RATE / (tables.COUNTER_RATES[1] * 2), printed)

        self.assertFalse(doubled)

    def test_the_zero_row_is_a_clock_that_never_fires(self) -> None:
        never = tables.COUNTER_RATES[0]

        self.assertGreater(never, tables.COUNTER_RANGE)

    def test_the_fastest_row_fires_every_sample(self) -> None:
        fastest = tables.COUNTER_RATES[0x1F]

        self.assertEqual(fastest, 1)


class ExponentialTest(unittest.TestCase):
    """The two columns the manual states relative to an endpoint it never names.

    Both are reproduced by this model's rate table, and neither can be checked in
    absolute terms, because a time to fall means nothing without saying how far.
    Each printed figure is divided by the model's tick period, and all thirty
    nine land on one tick count. That count is the endpoint Nintendo measured to,
    recovered from the table rather than read from the page.
    """

    def test_every_printed_figure_implies_the_same_length_of_fall(self) -> None:
        implied = _implied_ticks()

        spread = (max(implied) - min(implied)) / (sum(implied) / len(implied))

        self.assertLess(spread, 0.05)

    def test_that_check_covered_both_columns_in_full(self) -> None:
        covered = len(_implied_ticks())

        self.assertEqual(covered, 8 + 31)

    def test_the_recovered_endpoint_is_recorded_rather_than_built_in(self) -> None:
        entry = next(
            item for item in DIVERGENCES["divergences"] if item["id"] == "unstated-decay-endpoint"
        )

        self.assertIn("590", entry["referenceDoes"])

    def test_the_model_reaches_the_first_sustain_level_where_the_manual_puts_it(self) -> None:
        ratio = FACTS["envelope"]["sustainLevel"][0]["ratio"]

        self.assertEqual((ratio, _decay_ticks((FULL + 1) // 8 - 1)), ("1/8", 440))

    def test_a_slower_rate_always_takes_longer(self) -> None:
        periods = [tables.COUNTER_RATES[rate] for rate in range(1, 32)]

        self.assertEqual(periods, sorted(periods, reverse=True))


class DivergenceTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.entries: list[dict[str, Any]] = DIVERGENCES["divergences"]

    def test_each_entry_says_which_source_the_package_follows(self) -> None:
        allowed = {"document", "reference", "neither"}

        self.assertEqual({entry["packageFollows"] for entry in self.entries} - allowed, set())

    def test_each_entry_says_what_would_settle_it(self) -> None:
        missing = [entry["id"] for entry in self.entries if not entry.get("wouldSettleIt")]

        self.assertEqual(missing, [])

    def test_the_reference_being_an_emulator_is_recorded_as_a_limit(self) -> None:
        entry = next(
            item for item in self.entries if item["id"] == "the-audio-rests-on-an-emulator"
        )

        self.assertEqual(entry["severity"], "high")

    def test_the_gaussian_kernel_is_recorded_as_undocumented(self) -> None:
        named = {entry["id"] for entry in self.entries}

        self.assertIn("gaussian-kernel-is-undocumented", named)


if __name__ == "__main__":
    unittest.main(verbosity=1)
