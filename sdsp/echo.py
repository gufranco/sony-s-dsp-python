from .state import ECHO_DELAY_STEP, ECHO_HISTORY, REG_FLG, State
from .words import clamp16, signed8, signed16

REG_MVOLL = 0x0C
REG_EFB = 0x0D
REG_EVOLL = 0x2C
REG_ESA = 0x6D
REG_EDL = 0x7D
REG_FIR = 0x0F

EDL_MASK = 0x0F

FLG_MUTE = 0x40
FLG_ECHO_OFF = 0x20


class Echo(State):
    __slots__ = ()

    def _echo_address(self, channel: int) -> int:
        return (self.echo_pointer + channel * 2) & 0xFFFF

    def _echo_read(self, channel: int) -> None:
        at = self._echo_address(channel)
        sample = signed16(self.memory.read8(at) | (self.memory.read8((at + 1) & 0xFFFF) << 8))
        self.echo_history[self.echo_history_position][channel] = sample >> 1
        self.echo_history[self.echo_history_position + ECHO_HISTORY][channel] = sample >> 1

    def _fir(self, tap: int, channel: int) -> int:
        held = self.echo_history[self.echo_history_position + tap + 1][channel]
        return (held * signed8(self.registers[REG_FIR + tap * 0x10])) >> 6

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
        left = signed16(self.echo_in[0] + self._fir(6, 0))
        right = signed16(self.echo_in[1] + self._fir(6, 1))
        left += signed16(self._fir(7, 0))
        right += signed16(self._fir(7, 1))
        self.echo_in = [clamp16(left) & ~1, clamp16(right) & ~1]

    def _echo_output(self, channel: int) -> int:
        main = signed16(
            (self.main_out[channel] * signed8(self.registers[REG_MVOLL + channel * 0x10])) >> 7
        )
        echo = signed16(
            (self.echo_in[channel] * signed8(self.registers[REG_EVOLL + channel * 0x10])) >> 7
        )
        return clamp16(main + echo)

    def echo_26(self) -> None:
        self.main_out[0] = self._echo_output(0)
        feedback = signed8(self.registers[REG_EFB])
        left = self.echo_out[0] + signed16((self.echo_in[0] * feedback) >> 7)
        right = self.echo_out[1] + signed16((self.echo_in[1] * feedback) >> 7)
        self.echo_out = [clamp16(left) & ~1, clamp16(right) & ~1]

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
            self.echo_length = (self.registers[REG_EDL] & EDL_MASK) * ECHO_DELAY_STEP
        self.echo_offset += 4
        if self.echo_offset >= self.echo_length:
            self.echo_offset = 0
        self._echo_write(0)
        self.echo_enabled = self.registers[REG_FLG]

    def echo_30(self) -> None:
        self._echo_write(1)
