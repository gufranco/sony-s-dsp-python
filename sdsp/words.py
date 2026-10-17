def clamp16(value: int) -> int:
    if value > 0x7FFF:
        return 0x7FFF
    if value < -0x8000:
        return -0x8000
    return value


def signed8(value: int) -> int:
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def signed16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value
