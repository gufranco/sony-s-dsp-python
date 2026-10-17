import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.register_rig import (
    ECHO,
    ECHO_SPAN,
    LOUD,
    NEWEST_TAP,
    SETTLE,
    UNTOUCHED,
    a_memory,
    a_part,
    at,
    keyed,
    numbers_in,
    own_side_and_other,
    quoted,
    register_map,
)
from sdsp import core, echo, state
from sdsp.memory import Memory

MAP = register_map()


def echoing(fill: int = 0x24) -> tuple[core.Chip, Memory]:
    memory = Memory(fill=fill)
    chip = core.Chip(memory).reset()
    chip.write(state.REG_FLG, echo.FLG_ECHO_OFF)
    chip.write(echo.REG_EVOLL, LOUD)
    chip.write(echo.REG_EVOLL + 0x10, LOUD)
    chip.write(echo.REG_ESA, ECHO)
    chip.write(echo.REG_EDL, 1)
    return chip, memory


def an_echo_volume_silences(address: int, quote: str) -> list[bool]:
    chip, _ = echoing()
    chip.write(NEWEST_TAP, LOUD)
    chip.write(address, 0)
    return own_side_and_other(chip.render(SETTLE), quote)


def fed_back(address: int, value: int) -> bytes:
    chip, memory = echoing()
    chip.write(NEWEST_TAP, LOUD)
    chip.write(state.REG_FLG, 0)
    chip.write(address, value)
    chip.render(4)
    return bytes(memory.data[ECHO * 0x100 + 4 : ECHO * 0x100 + 16])


def echo_reached(address: int, value: int) -> bool:
    memory = a_memory()
    chip = keyed(a_part(memory))
    chip.write(echo.REG_ESA, ECHO)
    chip.write(echo.REG_EDL, 1)
    chip.write(state.REG_FLG, 0)
    chip.write(address, value)
    chip.render(64)
    return any(memory.data[ECHO * 0x100 : ECHO * 0x100 + ECHO_SPAN])


def echo_lands(address: int, page: int) -> int:
    chip, memory = echoing(UNTOUCHED)
    chip.write(state.REG_FLG, 0)
    chip.write(address, page)
    chip.render(4)
    return max(at for at, value in enumerate(memory.data) if value != UNTOUCHED) >> 8


def echo_written(address: int, value: int) -> int:
    chip, memory = echoing(UNTOUCHED)
    chip.write(state.REG_FLG, 0)
    chip.write(address, value)
    chip.render(600)
    return sum(1 for byte in memory.data if byte != UNTOUCHED)


def filtered(address: int) -> tuple[int, int]:
    chip, _ = echoing()
    chip.write(address, 0x40)
    rendered = chip.render(SETTLE)
    return rendered[-2], rendered[-1]


class EchoRegisterTest(unittest.TestCase):
    def test_the_left_echo_volume_reaches_its_own_channel_alone(self) -> None:
        # Arrange
        address, quote = at("global", "EVOL (L)"), quoted("global", "EVOL (L)")

        # Act
        found = an_echo_volume_silences(address, quote)

        # Assert
        self.assertEqual(found, [True, False])

    def test_the_right_echo_volume_reaches_its_own_channel_alone(self) -> None:
        # Arrange
        address, quote = at("global", "EVOL (R)"), quoted("global", "EVOL (R)")

        # Act
        found = an_echo_volume_silences(address, quote)

        # Assert
        self.assertEqual(found, [True, False])

    def test_echo_feedback_returns_the_echo_into_the_buffer(self) -> None:
        # Arrange
        address = at("global", "EFB")

        # Act
        found = [fed_back(address, value) for value in (0x00, 0x40)]

        # Assert
        self.assertEqual((found[0], found[1] == bytes(12)), (bytes(12), False))

    def test_echo_on_decides_whether_a_voice_reaches_the_echo_buffer(self) -> None:
        # Arrange
        address = at("global", "EON")

        # Act
        found = [echo_reached(address, value) for value in (0x00, 0x01)]

        # Assert
        self.assertEqual(found, [False, True])

    def test_the_echo_region_starts_at_the_page_the_offset_names(self) -> None:
        # Arrange
        address = at("global", "ESA")

        # Act
        found = [echo_lands(address, page) for page in (0x40, 0x50)]

        # Assert
        self.assertEqual(found, [0x40, 0x50])

    def test_only_the_printed_low_bits_of_the_echo_delay_count(self) -> None:
        # Arrange
        address = at("global", "EDL")
        bits = numbers_in(quoted("global", "EDL"))[0]
        delays = (1, 1 | 1 << bits, 1 | 1 << (bits - 1))

        # Act
        found = [echo_written(address, delay) for delay in delays]

        # Assert
        self.assertEqual((found[1] == found[0], found[2] == found[0]), (True, False))

    def test_each_coefficient_is_a_tap_shared_by_both_channels(self) -> None:
        # Arrange
        coefficients = MAP["filterCoefficients"]
        taps = numbers_in(coefficients["quote"])[0]

        # Act
        found = [filtered(int(address, 16)) for address in coefficients["addresses"]]

        # Assert
        self.assertEqual(
            [(left == right, left != 0) for left, right in found], [(True, True)] * taps
        )


if __name__ == "__main__":
    unittest.main()
