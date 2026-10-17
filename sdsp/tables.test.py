import sys
import unittest
from itertools import pairwise
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sdsp

COUNTER_RANGE = 30720

KERNEL_LENGTH = 512

UNIT = 2048


def taps_at(offset: int) -> tuple[int, int, int, int]:
    kernel = sdsp.GAUSSIAN
    return (kernel[255 - offset], kernel[511 - offset], kernel[256 + offset], kernel[offset])


def refusal(table: list[int] | tuple[int, ...]) -> str:
    try:
        sdsp.check_kernel(table)
    except sdsp.NotAKernel as error:
        return str(error)
    return ""


def changed(at: int, value: int) -> list[int]:
    table = list(sdsp.GAUSSIAN)
    table[at] = value
    return table


class GaussianTest(unittest.TestCase):
    def test_the_kernel_is_a_quarter_of_the_curve(self) -> None:
        # Arrange
        kernel = sdsp.GAUSSIAN

        # Act
        found = len(kernel)

        # Assert
        self.assertEqual(found, KERNEL_LENGTH)

    def test_the_kernel_rises_to_its_peak_at_the_end(self) -> None:
        # Arrange
        kernel = sdsp.GAUSSIAN

        # Act
        peak = max(kernel)

        # Assert
        self.assertEqual(kernel[-1], peak)

    def test_the_kernel_starts_at_nothing(self) -> None:
        # Arrange
        kernel = sdsp.GAUSSIAN

        # Act
        first = kernel[0]

        # Assert
        self.assertEqual(first, 0)

    def test_the_kernel_never_decreases(self) -> None:
        # Arrange
        kernel = sdsp.GAUSSIAN

        # Act
        falling = [index for index, (one, two) in enumerate(pairwise(kernel)) if two < one]

        # Assert
        self.assertEqual(falling, [])

    def test_the_four_taps_of_any_position_sum_to_one_unit(self) -> None:
        # Arrange
        positions = range(256)

        # Act
        apart = [offset for offset in positions if abs(sum(taps_at(offset)) / UNIT - 1) > 0.002]

        # Assert
        self.assertEqual(apart, [])

    def test_every_tap_fits_a_signed_word(self) -> None:
        # Arrange
        kernel = sdsp.GAUSSIAN

        # Act
        outside = [value for value in kernel if not -0x8000 <= value < 0x8000]

        # Assert
        self.assertEqual(outside, [])


class CounterTest(unittest.TestCase):
    def test_there_is_a_rate_for_every_five_bit_value(self) -> None:
        # Arrange
        rates = sdsp.COUNTER_RATES

        # Act
        found = len(rates)

        # Assert
        self.assertEqual(found, 32)

    def test_there_is_an_offset_for_every_rate(self) -> None:
        # Arrange
        offsets = sdsp.COUNTER_OFFSETS

        # Act
        found = len(offsets)

        # Assert
        self.assertEqual(found, 32)

    def test_the_slowest_rate_never_fires(self) -> None:
        # Arrange
        rates = sdsp.COUNTER_RATES

        # Act
        slowest = rates[0]

        # Assert
        self.assertGreater(slowest, COUNTER_RANGE)

    def test_the_fastest_rate_fires_every_sample(self) -> None:
        # Arrange
        rates = sdsp.COUNTER_RATES

        # Act
        fastest = rates[-1]

        # Assert
        self.assertEqual(fastest, 1)

    def test_every_firing_rate_divides_the_counter_range(self) -> None:
        # Arrange
        rates = sdsp.COUNTER_RATES[1:]

        # Act
        undivided = [rate for rate in rates if COUNTER_RANGE % rate != 0]

        # Assert
        self.assertEqual(undivided, [])

    def test_the_rates_never_get_slower_as_the_number_rises(self) -> None:
        # Arrange
        rates = sdsp.COUNTER_RATES[1:]

        # Act
        rising = [index for index, (one, two) in enumerate(pairwise(rates)) if two > one]

        # Assert
        self.assertEqual(rising, [])

    def test_the_offsets_repeat_a_short_stagger_pattern(self) -> None:
        # Arrange
        offsets = sdsp.COUNTER_OFFSETS[1:]

        # Act
        found = set(offsets)

        # Assert
        self.assertEqual(found, {0, 536, 1040})

    def test_the_stagger_cycles_every_three_rates(self) -> None:
        # Arrange
        middle = sdsp.COUNTER_OFFSETS[1:28]

        # Act
        cycled = tuple(middle[index % 3] for index in range(len(middle)))

        # Assert
        self.assertEqual(middle, cycled)

    def test_an_offset_larger_than_its_rate_is_taken_modulo_it(self) -> None:
        # Arrange
        rates = range(1, 32)

        # Act
        wrapping = [
            rate for rate in rates if sdsp.COUNTER_OFFSETS[rate] >= sdsp.COUNTER_RATES[rate]
        ]

        # Assert
        self.assertGreater(len(wrapping), 0)


class SuppliedKernelTest(unittest.TestCase):
    def test_the_published_table_passes_its_own_gate(self) -> None:
        # Arrange
        published = sdsp.GAUSSIAN

        # Act
        found = sdsp.check_kernel(published)

        # Assert
        self.assertEqual(found, published)

    def test_a_list_is_handed_back_as_a_tuple(self) -> None:
        # Arrange
        supplied = list(sdsp.GAUSSIAN)

        # Act
        found = sdsp.check_kernel(supplied)

        # Assert
        self.assertIsInstance(found, tuple)

    def test_a_table_of_the_wrong_length_is_refused(self) -> None:
        # Arrange
        short = sdsp.GAUSSIAN[:-1]

        # Act
        said = refusal(short)

        # Assert
        self.assertIn("511", said)

    def test_a_table_that_dips_is_refused(self) -> None:
        # Arrange
        dipping = changed(300, 0)

        # Act
        said = refusal(dipping)

        # Assert
        self.assertIn("300", said)

    def test_a_tap_outside_a_signed_word_is_refused(self) -> None:
        # Arrange
        wide = changed(-1, 0x8000)

        # Act
        said = refusal(wide)

        # Assert
        self.assertIn("signed word", said)

    def test_a_table_whose_taps_do_not_sum_to_unity_is_refused(self) -> None:
        # Arrange
        halved = [value // 2 for value in sdsp.GAUSSIAN]

        # Act
        said = refusal(halved)

        # Assert
        self.assertIn("sum to", said)

    def test_the_refusal_names_the_position_that_failed(self) -> None:
        # Arrange
        bent = changed(511, sdsp.GAUSSIAN[511] + 200)

        # Act
        said = refusal(bent)

        # Assert
        self.assertIn("position 0", said)

    def test_a_rounding_difference_inside_the_tolerance_is_allowed(self) -> None:
        # Arrange
        nudged = changed(511, sdsp.GAUSSIAN[511] + 1)

        # Act
        said = refusal(nudged)

        # Assert
        self.assertEqual(said, "")


if __name__ == "__main__":
    unittest.main()
