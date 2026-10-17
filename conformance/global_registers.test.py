import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sdsp
from conformance.register_rig import (
    ECHO,
    ECHO_SPAN,
    LOUD,
    NEWEST_TAP,
    QUIET,
    SETTLE,
    SHORT,
    STEADY,
    UNTOUCHED,
    a_memory,
    a_part,
    a_volume_silences,
    an_entry,
    at,
    consumed,
    contents,
    each_sample,
    keyed,
    numbers_in,
    quoted,
    silent,
    voiced,
)

ESA = at("global", "ESA")
EDL = at("global", "EDL")
EON = at("global", "EON")
NON = at("global", "NON")
KON = at("global", "KON")
FLG = at("global", "FLG")
OUTX = at("voice", "OUTX")


def keyed_by(address: int, value: int) -> list[int]:
    chip = voiced(a_part(), 0xFF)
    chip.write(address, value)
    chip.render(4)
    return [voice.index for voice in chip.voices if voice.envelope_mode == sdsp.ENV_ATTACK]


def flag_effects(address: int, flags: int) -> tuple[bool, bool, bool, bool]:
    memory = a_memory(fill=UNTOUCHED)
    chip = keyed(a_part(memory), 0x03)
    chip.write(NON, 0x02)
    chip.write(ESA, ECHO)
    chip.write(EDL, 1)
    chip.render(SETTLE)
    chip.write(address, flags)
    noise = each_sample(chip, 32, lambda: chip.read(chip.voices[1].base + OUTX))
    rendered = chip.render(32)
    return (
        chip.voices[0].envelope_mode == sdsp.ENV_RELEASE,
        silent(rendered),
        contents(memory, ECHO * 0x100, ECHO_SPAN) != bytes([UNTOUCHED]) * ECHO_SPAN,
        len(set(noise[-16:])) > 1,
    )


def everything_after(address: int, value: int) -> tuple[list[int], bytes, bytes]:
    memory = a_memory()
    chip = keyed(a_part(memory))
    chip.write(ESA, ECHO)
    chip.write(EON, 0x01)
    chip.write(at("global", "EVOL (L)"), LOUD)
    chip.write(NEWEST_TAP, LOUD)
    chip.write(FLG, 0)
    chip.write(address, value)
    rendered = chip.render(64)
    others = chip.registers[:address] + chip.registers[address + 1 :]
    return rendered, contents(memory), bytes(others)


def modulated(address: int, pmon: int, modulator_gain: int) -> int:
    chip = voiced(a_part(), 0x01, STEADY, modulator_gain)
    keyed(chip, 0x02)
    chip.write(KON, 0x03)
    chip.write(address, pmon)
    chip.render(256)
    return consumed(chip.voices[1])


def noisy(address: int, value: int) -> list[int]:
    chip = keyed(a_part(), 0xFF, QUIET)
    chip.write(address, value)
    chip.render(SETTLE)
    return [voice.index for voice in chip.voices if chip.read(voice.base + OUTX)]


def played_from(address: int, page: int) -> int:
    memory = a_memory()
    an_entry(memory, 0x30, 0, QUIET)
    an_entry(memory, 0x31, 0, SHORT)
    chip = keyed(a_part(memory))
    chip.write(address, page)
    chip.render(SETTLE)
    return chip.voices[0].brr_address & ~0xFF


class GlobalRegisterTest(unittest.TestCase):
    def test_the_left_main_volume_reaches_its_own_channel_alone(self) -> None:
        # Arrange
        address, quote = at("global", "MVOL (L)"), quoted("global", "MVOL (L)")

        # Act
        found = a_volume_silences(address, quote)

        # Assert
        self.assertEqual(found, [True, False])

    def test_the_right_main_volume_reaches_its_own_channel_alone(self) -> None:
        # Arrange
        address, quote = at("global", "MVOL (R)"), quoted("global", "MVOL (R)")

        # Act
        found = a_volume_silences(address, quote)

        # Assert
        self.assertEqual(found, [True, False])

    def test_each_key_on_bit_keys_the_voice_printed_beside_it(self) -> None:
        # Arrange
        first_bit, last_bit, first_voice, _ = numbers_in(quoted("global", "KON"))
        address = at("global", "KON")

        # Act
        found = [keyed_by(address, 1 << bit) for bit in range(first_bit, last_bit + 1)]

        # Assert
        self.assertEqual(found, [[first_voice + n] for n in range(last_bit - first_bit + 1)])

    def test_key_off_releases_a_sounding_voice_to_nothing(self) -> None:
        # Arrange
        chip = keyed(a_part())
        chip.render(SETTLE)
        sounding = chip.voices[0].envelope
        chip.write(at("global", "KOF"), 0x01)

        # Act
        chip.render(300)

        # Assert
        self.assertEqual(
            (sounding > 0, chip.voices[0].envelope_mode, chip.voices[0].envelope),
            (True, sdsp.ENV_RELEASE, 0),
        )

    def test_the_flag_register_switches_reset_mute_echo_and_noise_clock(self) -> None:
        # Arrange
        address = at("global", "FLG")
        flags = (0x80, 0x40, 0x20, 0x1F, 0x00)

        # Act
        found = [flag_effects(address, value) for value in flags]

        # Assert
        self.assertEqual(
            found,
            [
                (True, True, True, False),
                (False, True, True, False),
                (False, False, False, False),
                (False, False, True, True),
                (False, False, True, False),
            ],
        )

    def test_the_end_flag_rises_once_the_source_passes_its_end_block(self) -> None:
        # Arrange
        endx = at("global", "ENDX")
        chip = keyed(a_part(), source=SHORT)

        # Act
        found = each_sample(chip, 64, lambda: chip.read(endx) & 0x01)

        # Assert
        self.assertEqual((found[0], found[-1], found == sorted(found)), (0, 1, True))

    def test_the_register_printed_as_not_used_changes_nothing(self) -> None:
        # Arrange
        address = at("global", "---")

        # Act
        found = [everything_after(address, value) for value in (0x00, 0xFF)]

        # Assert
        self.assertEqual(found[0], found[1])

    def test_pitch_modulation_follows_the_output_of_the_voice_before(self) -> None:
        # Arrange
        address = at("global", "PMON")
        second_voice = 0x02

        # Act
        found = [
            modulated(address, 0x00, LOUD),
            modulated(address, second_voice, LOUD),
            modulated(address, second_voice, 0),
        ]

        # Assert
        self.assertEqual((found[1] == found[0], found[2] == found[0]), (False, True))

    def test_each_noise_bit_turns_noise_on_for_the_voice_printed_beside_it(self) -> None:
        # Arrange
        first_bit, last_bit, first_voice, _ = numbers_in(quoted("global", "NON"))
        address = at("global", "NON")

        # Act
        found = [noisy(address, 1 << bit) for bit in range(first_bit, last_bit + 1)]

        # Assert
        self.assertEqual(found, [[first_voice + n] for n in range(last_bit - first_bit + 1)])

    def test_the_directory_is_read_from_the_page_the_offset_names(self) -> None:
        # Arrange
        address = at("global", "DIR")

        # Act
        found = [played_from(address, page) for page in (0x30, 0x31)]

        # Assert
        self.assertEqual(found, [QUIET, SHORT])


if __name__ == "__main__":
    unittest.main()
