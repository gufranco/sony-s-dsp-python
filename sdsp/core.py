"""An S-DSP that runs on the schedule the hardware runs on.

Every sample takes thirty two clocks, and the eight voices are not processed one
after another inside them. They are pipelined: at any clock one voice is reading
its sample pointer while another decodes its block and a third writes its output.
`PIPELINE` at the bottom of this file is that ordering, one entry per clock,
taken from the hardware.

Modelling it as a loop over voices would be shorter and would be wrong in ways
that only appear on real music. A voice under pitch modulation reads the previous
voice's output from whichever clock it lands on. Key on is sampled every other
sample rather than every sample. The end of sample flag reaches its register two
clocks after the voice that set it. None of that survives the simplification, and
all of it is audible.

Nothing here starts clean. Audio RAM holds whatever it held, and the registers a
reset does not define hold whatever they held.
"""

from collections.abc import Callable
from typing import Protocol

from .memory import UNSET_SEED, scramble
from .tables import COUNTER_OFFSETS, COUNTER_RANGE, COUNTER_RATES, GAUSSIAN

Step = Callable[["Dsp"], None]
"""One entry of the thirty two step cycle the DSP walks per sample."""


class MemoryLike(Protocol):
    """The whole of what the DSP needs from the audio RAM it is wired to.

    Naming the two methods rather than the class keeps a caller free to supply
    real RAM, a test double, or the memory of a running SPC700, and keeps this
    module from importing any of them.
    """

    def read8(self, address: int) -> int: ...

    def write8(self, address: int, value: int) -> None: ...


REGISTER_COUNT = 128
VOICE_COUNT = 8

BRR_BLOCK_BYTES = 9
BRR_BUFFER = 12

ENV_RELEASE = 0
ENV_ATTACK = 1
ENV_DECAY = 2
ENV_SUSTAIN = 3

REG_MVOLL = 0x0C
REG_EFB = 0x0D
REG_EVOLL = 0x2C
REG_PMON = 0x2D
REG_NON = 0x3D
REG_EON = 0x4D
REG_DIR = 0x5D
REG_ESA = 0x6D
REG_EDL = 0x7D
REG_KON = 0x4C
REG_KOFF = 0x5C
REG_FLG = 0x6C
REG_ENDX = 0x7C
REG_FIR = 0x0F

V_VOLL = 0x00
V_PITCHL = 0x02
V_PITCHH = 0x03
V_SRCN = 0x04
V_ADSR0 = 0x05
V_ADSR1 = 0x06
V_GAIN = 0x07
V_ENVX = 0x08
V_OUTX = 0x09

FLG_RESET = 0x80
FLG_MUTE = 0x40
FLG_ECHO_OFF = 0x20

ECHO_HISTORY = 8

RESET_FLAGS = 0xE0


def _clamp16(value: int) -> int:
    if value > 0x7FFF:
        return 0x7FFF
    if value < -0x8000:
        return -0x8000
    return value


def _signed8(value: int) -> int:
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def _signed16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


class Voice:
    """One of the eight voices, and everything it carries between samples."""

    def __init__(self, index: int) -> None:
        self.index = index
        self.bit = 1 << index
        self.base = index * 0x10
        self.buffer = [0] * (BRR_BUFFER * 2)
        self.buffer_position = 0
        self.interpolation = 0
        self.brr_address = 0
        self.brr_offset = 1
        self.key_on_delay = 0
        self.envelope_mode = ENV_RELEASE
        self.envelope = 0
        self.hidden_envelope = 0
        self.envelope_out = 0


class Dsp:
    """An S-DSP holding whatever it was holding, which is how one powers up."""

    def __init__(self, memory: MemoryLike, seed: int = UNSET_SEED, reset: bool = True) -> None:
        self.memory = memory
        self.registers = bytearray(scramble(REGISTER_COUNT, seed))
        self.voices = [Voice(index) for index in range(VOICE_COUNT)]
        self.model = "s-dsp"
        self._clear_state()
        if reset:
            self.reset()

    def _clear_state(self) -> None:
        self.phase = 0
        self.counter = 0
        self.noise = 0x4000
        self.every_other_sample = 1
        self.kon = 0
        self.new_kon = 0
        self.kon_check = False
        self.echo_offset = 0
        self.echo_length = 0
        self.echo_history = [[0, 0] for _ in range(ECHO_HISTORY * 2)]
        self.echo_history_position = 0
        self.main_out = [0, 0]
        self.echo_out = [0, 0]
        self.echo_in = [0, 0]
        self.echo_pointer = 0
        self.echo_enabled = 0
        self.t_pmon = 0
        self.t_non = 0
        self.t_eon = 0
        self.t_dir = 0
        self.t_koff = 0
        self.t_esa = 0
        self.t_srcn = 0
        self.t_dir_address = 0
        self.t_brr_next_address = 0
        self.t_adsr0 = 0
        self.t_pitch = 0
        self.t_brr_byte = 0
        self.t_brr_header = 0
        self.t_output = 0
        self.t_looped = 0
        self.endx_buffer = 0
        self.outx_buffer = 0
        self.envx_buffer = 0
        self.rendered: list[int] = []

    def reset(self) -> None:
        """Put the DSP where a reset puts it, which is quiet and released."""
        self._clear_state()
        for index in range(REGISTER_COUNT):
            self.registers[index] = 0
        self.registers[REG_FLG] = RESET_FLAGS
        for voice in self.voices:
            voice.buffer = [0] * (BRR_BUFFER * 2)
            voice.buffer_position = 0
            voice.interpolation = 0
            voice.brr_address = 0
            voice.brr_offset = 1
            voice.key_on_delay = 0
            voice.envelope_mode = ENV_RELEASE
            voice.envelope = 0
            voice.hidden_envelope = 0
            voice.envelope_out = 0

    def read(self, address: int) -> int:
        return self.registers[address & 0x7F]

    def write(self, address: int, value: int) -> None:
        """Take a register write, and act on the ones that are not just storage."""
        address &= 0x7F
        value &= 0xFF
        self.registers[address] = value
        if address == REG_KON:
            self.new_kon = value
        elif address == REG_ENDX:
            self.registers[REG_ENDX] = 0
            self.endx_buffer = 0

    def _voice_register(self, voice: Voice, offset: int) -> int:
        return self.registers[voice.base + offset]

    def _read_counter(self, rate: int) -> bool:
        if rate == 0:
            return True
        return bool((self.counter + COUNTER_OFFSETS[rate]) % COUNTER_RATES[rate])

    def _run_counters(self) -> None:
        self.counter = (self.counter - 1) % COUNTER_RANGE

    def _interpolate(self, voice: Voice) -> int:
        position = voice.interpolation
        at = (position >> 12) + voice.buffer_position
        offset = position >> 4 & 0xFF
        forward = 255 - offset
        reverse = offset

        out = (GAUSSIAN[forward] * voice.buffer[at]) >> 11
        out += (GAUSSIAN[forward + 256] * voice.buffer[at + 1]) >> 11
        out += (GAUSSIAN[reverse + 256] * voice.buffer[at + 2]) >> 11
        out = _signed16(out)
        out += (GAUSSIAN[reverse] * voice.buffer[at + 3]) >> 11
        return _clamp16(out) & ~1

    def _decode_brr(self, voice: Voice) -> None:
        """Expand four samples of a block, filtering against the two before them."""
        nybbles = self.t_brr_byte * 0x100 + self.memory.read8(
            (voice.brr_address + voice.brr_offset + 1) & 0xFFFF
        )
        header = self.t_brr_header

        at = voice.buffer_position
        voice.buffer_position += 4
        if voice.buffer_position >= BRR_BUFFER:
            voice.buffer_position = 0

        for _ in range(4):
            sample = _signed16(nybbles) >> 12
            nybbles = (nybbles << 4) & 0xFFFFF

            shift = header >> 4
            if shift <= 12:
                sample = (sample << shift) >> 1
            else:
                sample &= ~0x7FF

            first = voice.buffer[at + BRR_BUFFER - 1]
            second = voice.buffer[at + BRR_BUFFER - 2] >> 1
            kind = header & 0x0C
            if kind >= 8:
                sample += first
                sample -= second
                if kind == 8:
                    sample += second >> 4
                    sample += (first * -3) >> 6
                else:
                    sample += (first * -13) >> 7
                    sample += (second * 3) >> 4
            elif kind:
                sample += first >> 1
                sample += (-first) >> 5

            sample = _signed16(_clamp16(sample) * 2)
            voice.buffer[at] = sample
            voice.buffer[at + BRR_BUFFER] = sample
            at += 1

    def _run_envelope(self, voice: Voice) -> None:
        envelope = voice.envelope
        if voice.envelope_mode == ENV_RELEASE:
            envelope -= 0x8
            voice.envelope = max(envelope, 0)
            return

        data = self._voice_register(voice, V_ADSR1)
        if self.t_adsr0 & 0x80:
            if voice.envelope_mode >= ENV_DECAY:
                envelope -= 1
                envelope -= envelope >> 8
                rate = data & 0x1F
                if voice.envelope_mode == ENV_DECAY:
                    rate = (self.t_adsr0 >> 3 & 0x0E) + 0x10
            else:
                rate = (self.t_adsr0 & 0x0F) * 2 + 1
                envelope += 0x20 if rate < 31 else 0x400
        else:
            data = self._voice_register(voice, V_GAIN)
            mode = data >> 5
            if mode < 4:
                envelope = data * 0x10
                rate = 31
            else:
                rate = data & 0x1F
                if mode == 4:
                    envelope -= 0x20
                elif mode < 6:
                    envelope -= 1
                    envelope -= envelope >> 8
                else:
                    envelope += 0x20
                    if mode > 6 and voice.hidden_envelope >= 0x600:
                        envelope += 0x8 - 0x20

        if (envelope >> 8) == (data >> 5) and voice.envelope_mode == ENV_DECAY:
            voice.envelope_mode = ENV_SUSTAIN

        voice.hidden_envelope = envelope

        if not 0 <= envelope <= 0x7FF:
            envelope = 0 if envelope < 0 else 0x7FF
            if voice.envelope_mode == ENV_ATTACK:
                voice.envelope_mode = ENV_DECAY

        if not self._read_counter(rate):
            voice.envelope = envelope

    def voice_1(self, voice: Voice) -> None:
        self.t_dir_address = (self.t_dir * 0x100 + self.t_srcn * 4) & 0xFFFF
        self.t_srcn = self._voice_register(voice, V_SRCN)

    def voice_2(self, voice: Voice) -> None:
        entry = self.t_dir_address
        if not voice.key_on_delay:
            entry += 2
        self.t_brr_next_address = self.memory.read8(entry & 0xFFFF) | (
            self.memory.read8((entry + 1) & 0xFFFF) << 8
        )
        self.t_adsr0 = self._voice_register(voice, V_ADSR0)
        self.t_pitch = self._voice_register(voice, V_PITCHL)

    def voice_3a(self, voice: Voice) -> None:
        self.t_pitch += (self._voice_register(voice, V_PITCHH) & 0x3F) << 8

    def voice_3b(self, voice: Voice) -> None:
        self.t_brr_byte = self.memory.read8((voice.brr_address + voice.brr_offset) & 0xFFFF)
        self.t_brr_header = self.memory.read8(voice.brr_address & 0xFFFF)

    def voice_3c(self, voice: Voice) -> None:
        if self.t_pmon & voice.bit:
            self.t_pitch += ((self.t_output >> 5) * self.t_pitch) >> 10

        if voice.key_on_delay:
            if voice.key_on_delay == 5:
                voice.brr_address = self.t_brr_next_address
                voice.brr_offset = 1
                voice.buffer_position = 0
                self.t_brr_header = 0
                self.kon_check = True

            voice.envelope = 0
            voice.hidden_envelope = 0
            voice.interpolation = 0
            voice.key_on_delay -= 1
            if voice.key_on_delay & 3:
                voice.interpolation = 0x4000
            self.t_pitch = 0

        output = self._interpolate(voice)
        if self.t_non & voice.bit:
            output = _signed16(self.noise * 2)

        self.t_output = (output * voice.envelope) >> 11 & ~1
        voice.envelope_out = (voice.envelope >> 4) & 0xFF

        if self.registers[REG_FLG] & FLG_RESET or (self.t_brr_header & 3) == 1:
            voice.envelope_mode = ENV_RELEASE
            voice.envelope = 0

        if self.every_other_sample:
            if self.t_koff & voice.bit:
                voice.envelope_mode = ENV_RELEASE
            if self.kon & voice.bit:
                voice.key_on_delay = 5
                voice.envelope_mode = ENV_ATTACK

        if not voice.key_on_delay:
            self._run_envelope(voice)

    def _voice_output(self, voice: Voice, channel: int) -> None:
        amplitude = (self.t_output * _signed8(self._voice_register(voice, V_VOLL + channel))) >> 7
        self.main_out[channel] = _clamp16(self.main_out[channel] + amplitude)
        if self.t_eon & voice.bit:
            self.echo_out[channel] = _clamp16(self.echo_out[channel] + amplitude)

    def voice_4(self, voice: Voice) -> None:
        self.t_looped = 0
        if voice.interpolation >= 0x4000:
            self._decode_brr(voice)
            voice.brr_offset += 2
            if voice.brr_offset >= BRR_BLOCK_BYTES:
                voice.brr_address = (voice.brr_address + BRR_BLOCK_BYTES) & 0xFFFF
                if self.t_brr_header & 1:
                    voice.brr_address = self.t_brr_next_address
                    self.t_looped = voice.bit
                voice.brr_offset = 1

        voice.interpolation = (voice.interpolation & 0x3FFF) + self.t_pitch
        voice.interpolation = min(voice.interpolation, 0x7FFF)
        self._voice_output(voice, 0)

    def voice_5(self, voice: Voice) -> None:
        self._voice_output(voice, 1)
        endx = self.registers[REG_ENDX] | self.t_looped
        if voice.key_on_delay == 5:
            endx &= ~voice.bit
        self.endx_buffer = endx & 0xFF

    def voice_6(self, voice: Voice) -> None:
        self.outx_buffer = (self.t_output >> 8) & 0xFF

    def voice_7(self, voice: Voice) -> None:
        self.registers[REG_ENDX] = self.endx_buffer
        self.envx_buffer = voice.envelope_out

    def voice_8(self, voice: Voice) -> None:
        self.registers[voice.base + V_OUTX] = self.outx_buffer

    def voice_9(self, voice: Voice) -> None:
        self.registers[voice.base + V_ENVX] = self.envx_buffer

    def voice_3(self, voice: Voice) -> None:
        self.voice_3a(voice)
        self.voice_3b(voice)
        self.voice_3c(voice)

    def misc_27(self) -> None:
        self.t_pmon = self.registers[REG_PMON] & 0xFE

    def misc_28(self) -> None:
        self.t_non = self.registers[REG_NON]
        self.t_eon = self.registers[REG_EON]
        self.t_dir = self.registers[REG_DIR]

    def misc_29(self) -> None:
        self.every_other_sample ^= 1
        if self.every_other_sample:
            self.new_kon &= ~self.kon & 0xFF

    def misc_30(self) -> None:
        if self.every_other_sample:
            self.kon = self.new_kon
            self.t_koff = self.registers[REG_KOFF]
        self._run_counters()
        if not self._read_counter(self.registers[REG_FLG] & 0x1F):
            feedback = (self.noise << 13) ^ (self.noise << 14)
            self.noise = (feedback & 0x4000) ^ (self.noise >> 1)

    def _echo_address(self, channel: int) -> int:
        return (self.echo_pointer + channel * 2) & 0xFFFF

    def _echo_read(self, channel: int) -> None:
        at = self._echo_address(channel)
        sample = _signed16(self.memory.read8(at) | (self.memory.read8((at + 1) & 0xFFFF) << 8))
        self.echo_history[self.echo_history_position][channel] = sample >> 1
        self.echo_history[self.echo_history_position + ECHO_HISTORY][channel] = sample >> 1

    def _fir(self, tap: int, channel: int) -> int:
        held = self.echo_history[self.echo_history_position + tap + 1][channel]
        return (held * _signed8(self.registers[REG_FIR + tap * 0x10])) >> 6

    def echo_22(self) -> None:
        self.echo_history_position += 1
        if self.echo_history_position >= ECHO_HISTORY:
            self.echo_history_position = 0
        self.echo_pointer = (self.t_esa * 0x100 + self.echo_offset) & 0xFFFF
        self._echo_read(0)
        self.echo_in = [self._fir(0, 0), self._fir(0, 1)]

    def echo_23(self) -> None:
        self.echo_in[0] += self._fir(1, 0) + self._fir(2, 0)
        self.echo_in[1] += self._fir(1, 1) + self._fir(2, 1)
        self._echo_read(1)

    def echo_24(self) -> None:
        self.echo_in[0] += self._fir(3, 0) + self._fir(4, 0) + self._fir(5, 0)
        self.echo_in[1] += self._fir(3, 1) + self._fir(4, 1) + self._fir(5, 1)

    def echo_25(self) -> None:
        left = _signed16(self.echo_in[0] + self._fir(6, 0))
        right = _signed16(self.echo_in[1] + self._fir(6, 1))
        left += _signed16(self._fir(7, 0))
        right += _signed16(self._fir(7, 1))
        self.echo_in = [_clamp16(left) & ~1, _clamp16(right) & ~1]

    def _echo_output(self, channel: int) -> int:
        main = _signed16(
            (self.main_out[channel] * _signed8(self.registers[REG_MVOLL + channel * 0x10])) >> 7
        )
        echo = _signed16(
            (self.echo_in[channel] * _signed8(self.registers[REG_EVOLL + channel * 0x10])) >> 7
        )
        return _clamp16(main + echo)

    def echo_26(self) -> None:
        self.main_out[0] = self._echo_output(0)
        feedback = _signed8(self.registers[REG_EFB])
        left = self.echo_out[0] + _signed16((self.echo_in[0] * feedback) >> 7)
        right = self.echo_out[1] + _signed16((self.echo_in[1] * feedback) >> 7)
        self.echo_out = [_clamp16(left) & ~1, _clamp16(right) & ~1]

    def echo_27(self) -> None:
        left = self.main_out[0]
        right = self._echo_output(1)
        self.main_out = [0, 0]
        if self.registers[REG_FLG] & FLG_MUTE:
            left = 0
            right = 0
        self.rendered.append(left)
        self.rendered.append(right)

    def echo_28(self) -> None:
        self.echo_enabled = self.registers[REG_FLG]

    def _echo_write(self, channel: int) -> None:
        if not self.echo_enabled & FLG_ECHO_OFF:
            at = self._echo_address(channel)
            value = self.echo_out[channel] & 0xFFFF
            self.memory.write8(at, value & 0xFF)
            self.memory.write8((at + 1) & 0xFFFF, value >> 8)
        self.echo_out[channel] = 0

    def echo_29(self) -> None:
        self.t_esa = self.registers[REG_ESA]
        if not self.echo_offset:
            self.echo_length = (self.registers[REG_EDL] & 0x0F) * 0x800
        self.echo_offset += 4
        if self.echo_offset >= self.echo_length:
            self.echo_offset = 0
        self._echo_write(0)
        self.echo_enabled = self.registers[REG_FLG]

    def echo_30(self) -> None:
        self._echo_write(1)

    def clock(self) -> None:
        """One of the thirty two clocks a sample is made of."""
        for step in SCHEDULE[self.phase]:
            step(self)
        self.phase = (self.phase + 1) & 31

    def run(self, clocks: int) -> None:
        """Run for that many clocks, thirty two of which make one sample."""
        for _ in range(clocks):
            self.clock()

    def render(self, samples: int) -> list[int]:
        """Run long enough to produce that many stereo samples, and return them."""
        self.rendered = []
        self.run(samples * 32)
        return list(self.rendered)


def _voice_step(name: str, index: int) -> "Step":
    def run(dsp: "Dsp") -> None:
        getattr(dsp, name)(dsp.voices[index])

    return run


def _plain_step(name: str) -> "Step":
    def run(dsp: "Dsp") -> None:
        getattr(dsp, name)()

    return run


PIPELINE: dict[int, list[str | tuple[str, int]]] = {
    0: [("voice_5", 0), ("voice_2", 1)],
    1: [("voice_6", 0), ("voice_3", 1)],
    2: [("voice_7", 0), ("voice_1", 3), ("voice_4", 1)],
    3: [("voice_8", 0), ("voice_5", 1), ("voice_2", 2)],
    4: [("voice_9", 0), ("voice_6", 1), ("voice_3", 2)],
    5: [("voice_7", 1), ("voice_1", 4), ("voice_4", 2)],
    6: [("voice_8", 1), ("voice_5", 2), ("voice_2", 3)],
    7: [("voice_9", 1), ("voice_6", 2), ("voice_3", 3)],
    8: [("voice_7", 2), ("voice_1", 5), ("voice_4", 3)],
    9: [("voice_8", 2), ("voice_5", 3), ("voice_2", 4)],
    10: [("voice_9", 2), ("voice_6", 3), ("voice_3", 4)],
    11: [("voice_7", 3), ("voice_1", 6), ("voice_4", 4)],
    12: [("voice_8", 3), ("voice_5", 4), ("voice_2", 5)],
    13: [("voice_9", 3), ("voice_6", 4), ("voice_3", 5)],
    14: [("voice_7", 4), ("voice_1", 7), ("voice_4", 5)],
    15: [("voice_8", 4), ("voice_5", 5), ("voice_2", 6)],
    16: [("voice_9", 4), ("voice_6", 5), ("voice_3", 6)],
    17: [("voice_1", 0), ("voice_7", 5), ("voice_4", 6)],
    18: [("voice_8", 5), ("voice_5", 6), ("voice_2", 7)],
    19: [("voice_9", 5), ("voice_6", 6), ("voice_3", 7)],
    20: [("voice_1", 1), ("voice_7", 6), ("voice_4", 7)],
    21: [("voice_8", 6), ("voice_5", 7), ("voice_2", 0)],
    22: [("voice_3a", 0), ("voice_9", 6), ("voice_6", 7), "echo_22"],
    23: [("voice_7", 7), "echo_23"],
    24: [("voice_8", 7), "echo_24"],
    25: [("voice_3b", 0), ("voice_9", 7), "echo_25"],
    26: ["echo_26"],
    27: ["misc_27", "echo_27"],
    28: ["misc_28", "echo_28"],
    29: ["misc_29", "echo_29"],
    30: ["misc_30", ("voice_3c", 0), "echo_30"],
    31: [("voice_4", 0), ("voice_1", 2)],
}
"""What runs on each of the thirty two clocks, and for which voice.

Reading it down the page shows why a loop over voices cannot stand in for it. On
clock 17 voice 0 is fetching its sample pointer while voice 5 writes a register
and voice 6 mixes its output, and all three belong to the same sample.
"""

SCHEDULE = tuple(
    tuple(
        _plain_step(entry) if isinstance(entry, str) else _voice_step(*entry)
        for entry in PIPELINE[clock]
    )
    for clock in range(32)
)
