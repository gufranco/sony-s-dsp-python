#ifndef SDSP_REF_SNES9X_STUB_H
#define SDSP_REF_SNES9X_STUB_H

#include <cstddef>
#include <cstdint>
#include <vector>

class Resampler {
  public:
    std::vector<short> taken;

    void push_sample(short left, short right) {
        taken.push_back(left);
        taken.push_back(right);
    }

    void clear() { taken.clear(); }
};

struct SSettings {
    bool MSU1;
    bool SeparateEchoBuffer;
    int  InterpolationMethod;
    bool DisableSampleCaching;
    bool DisableMasterVolume;
    bool SoundSync;
    bool Mute;
};

extern struct SSettings Settings;

void S9xMSU1Generate(size_t);

#endif
