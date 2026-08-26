import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sdsp import tables
from sdsp.errors import NotAKernel


class GaussianTest(unittest.TestCase):
    def test_the_kernel_is_a_quarter_of_the_curve(self) -> None:
        self.assertEqual(len(tables.GAUSSIAN), 512)

    def test_the_kernel_rises_to_its_peak_at_the_end(self) -> None:
        self.assertEqual(tables.GAUSSIAN[-1], max(tables.GAUSSIAN))

    def test_the_kernel_starts_at_nothing(self) -> None:
        self.assertEqual(tables.GAUSSIAN[0], 0)

    def test_the_kernel_never_decreases(self) -> None:
        falling = [
            index
            for index, (first, second) in enumerate(
                zip(tables.GAUSSIAN, tables.GAUSSIAN[1:], strict=False)
            )
            if second < first
        ]

        self.assertEqual(falling, [])

    def test_the_four_taps_of_any_position_sum_to_one_unit(self) -> None:
        for offset in range(256):
            taps = (
                tables.GAUSSIAN[255 - offset],
                tables.GAUSSIAN[511 - offset],
                tables.GAUSSIAN[256 + offset],
                tables.GAUSSIAN[offset],
            )

            self.assertAlmostEqual(sum(taps) / 2048, 1.0, delta=0.002)

    def test_every_tap_fits_a_signed_word(self) -> None:
        self.assertTrue(all(-0x8000 <= value < 0x8000 for value in tables.GAUSSIAN))


class CounterTest(unittest.TestCase):
    def test_there_is_a_rate_for_every_five_bit_value(self) -> None:
        self.assertEqual(len(tables.COUNTER_RATES), 32)

    def test_there_is_an_offset_for_every_rate(self) -> None:
        self.assertEqual(len(tables.COUNTER_OFFSETS), 32)

    def test_the_slowest_rate_never_fires(self) -> None:
        self.assertGreater(tables.COUNTER_RATES[0], tables.COUNTER_RANGE)

    def test_the_fastest_rate_fires_every_sample(self) -> None:
        self.assertEqual(tables.COUNTER_RATES[-1], 1)

    def test_every_firing_rate_divides_the_counter_range(self) -> None:
        undivided = [rate for rate in tables.COUNTER_RATES[1:] if tables.COUNTER_RANGE % rate != 0]

        self.assertEqual(undivided, [])

    def test_the_rates_never_get_slower_as_the_number_rises(self) -> None:
        rising = [
            index
            for index, (first, second) in enumerate(
                zip(tables.COUNTER_RATES[1:], tables.COUNTER_RATES[2:], strict=False)
            )
            if second > first
        ]

        self.assertEqual(rising, [])

    def test_the_offsets_repeat_a_short_stagger_pattern(self) -> None:
        self.assertEqual(set(tables.COUNTER_OFFSETS[1:]), {0, 536, 1040})

    def test_the_stagger_cycles_every_three_rates(self) -> None:
        middle = tables.COUNTER_OFFSETS[1:28]

        self.assertEqual(middle, tuple(middle[index % 3] for index in range(len(middle))))

    def test_an_offset_larger_than_its_rate_is_taken_modulo_it(self) -> None:
        wrapping = [
            rate
            for rate in range(1, 32)
            if tables.COUNTER_OFFSETS[rate] >= tables.COUNTER_RATES[rate]
        ]

        self.assertTrue(wrapping)

    def test_the_counter_range_is_what_the_rates_were_built_for(self) -> None:
        self.assertEqual(tables.COUNTER_RANGE, 30720)


class SuppliedKernelTest(unittest.TestCase):
    """That a caller's table is held to what the part's arithmetic requires.

    No digest can settle this one, so these are the whole of the gate. Each is
    driven against a table that breaks exactly that property, because a check
    nobody has seen refuse is not known to refuse.
    """

    def test_the_published_table_passes_its_own_gate(self) -> None:
        self.assertEqual(tables.check_kernel(tables.GAUSSIAN), tables.GAUSSIAN)

    def test_a_list_is_handed_back_as_a_tuple(self) -> None:
        self.assertIsInstance(tables.check_kernel(list(tables.GAUSSIAN)), tuple)

    def test_a_table_of_the_wrong_length_is_refused(self) -> None:
        with self.assertRaises(NotAKernel) as caught:
            tables.check_kernel(tables.GAUSSIAN[:-1])

        self.assertIn("511", str(caught.exception))

    def test_a_table_that_dips_is_refused(self) -> None:
        dipping = list(tables.GAUSSIAN)
        dipping[300] = 0

        with self.assertRaises(NotAKernel) as caught:
            tables.check_kernel(dipping)

        self.assertIn("300", str(caught.exception))

    def test_a_tap_outside_a_signed_word_is_refused(self) -> None:
        wide = list(tables.GAUSSIAN)
        wide[-1] = 0x8000

        with self.assertRaises(NotAKernel) as caught:
            tables.check_kernel(wide)

        self.assertIn("signed word", str(caught.exception))

    def test_a_table_whose_taps_do_not_sum_to_unity_is_refused(self) -> None:
        halved = [value // 2 for value in tables.GAUSSIAN]

        with self.assertRaises(NotAKernel) as caught:
            tables.check_kernel(halved)

        self.assertIn("sum to", str(caught.exception))

    def test_the_refusal_names_the_position_that_failed(self) -> None:
        bent = list(tables.GAUSSIAN)
        bent[511] = bent[511] + 200

        with self.assertRaises(NotAKernel) as caught:
            tables.check_kernel(bent)

        self.assertIn("position 0", str(caught.exception))

    def test_a_rounding_difference_inside_the_tolerance_is_allowed(self) -> None:
        nudged = list(tables.GAUSSIAN)
        nudged[511] = nudged[511] + 1

        self.assertEqual(len(tables.check_kernel(nudged)), tables.KERNEL_LENGTH)


if __name__ == "__main__":
    unittest.main()
