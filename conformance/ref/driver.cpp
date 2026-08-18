#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

#include "snes9x_stub.h"
#include "SPC_DSP.h"

struct SSettings Settings;
void S9xMSU1Generate(size_t) {}

static bool read_exact(void *dest, size_t size) {
    return fread(dest, 1, size, stdin) == size;
}

static bool read_u32(uint32_t *out) {
    unsigned char raw[4];
    if (!read_exact(raw, sizeof(raw))) {
        return false;
    }
    *out = (uint32_t)raw[0] | ((uint32_t)raw[1] << 8) | ((uint32_t)raw[2] << 16) |
           ((uint32_t)raw[3] << 24);
    return true;
}

int main(void) {
    Settings.InterpolationMethod = 2;

    uint32_t cases = 0;
    if (!read_u32(&cases)) {
        return 1;
    }

    for (uint32_t index = 0; index < cases; index++) {
        std::vector<unsigned char> ram(0x10000);
        if (!read_exact(ram.data(), ram.size())) {
            return 1;
        }

        unsigned char regs[SPC_DSP::register_count];
        if (!read_exact(regs, sizeof(regs))) {
            return 1;
        }

        uint32_t samples = 0;
        if (!read_u32(&samples)) {
            return 1;
        }

        SPC_DSP dsp;
        dsp.init(ram.data());
        dsp.reset();

        for (int at = 0; at < SPC_DSP::register_count; at++) {
            if (at != 0x4C && at != 0x5C) {
                dsp.write(at, regs[at]);
            }
        }
        dsp.write(0x5C, regs[0x5C]);
        dsp.write(0x4C, regs[0x4C]);

        Resampler sink;
        dsp.set_output(&sink);
        dsp.run((int)samples * 32);

        int produced = (int)sink.taken.size();
        uint32_t count = (uint32_t)produced;
        unsigned char header[4] = {
            (unsigned char)(count & 0xFF),
            (unsigned char)((count >> 8) & 0xFF),
            (unsigned char)((count >> 16) & 0xFF),
            (unsigned char)((count >> 24) & 0xFF),
        };
        if (fwrite(header, 1, sizeof(header), stdout) != sizeof(header)) {
            return 1;
        }
        for (int at = 0; at < produced; at++) {
            short value = sink.taken[at];
            unsigned char pair[2] = {
                (unsigned char)(value & 0xFF),
                (unsigned char)((value >> 8) & 0xFF),
            };
            if (fwrite(pair, 1, sizeof(pair), stdout) != sizeof(pair)) {
                return 1;
            }
        }
    }
    return 0;
}
