FROM debian:bookworm-slim AS build

ARG SNES9X_REF=1.63

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth=1 --branch "${SNES9X_REF}" \
        https://github.com/snes9xgit/snes9x.git /src/snes9x

WORKDIR /ref

RUN cp -f /src/snes9x/apu/bapu/dsp/SPC_DSP.cpp \
       /src/snes9x/apu/bapu/dsp/SPC_DSP.h \
       /src/snes9x/apu/bapu/dsp/blargg_common.h \
       /src/snes9x/apu/bapu/dsp/blargg_config.h \
       /src/snes9x/apu/bapu/dsp/blargg_endian.h \
       /src/snes9x/apu/bapu/dsp/blargg_source.h /ref/ \
    && sha256sum /ref/SPC_DSP.cpp

COPY driver.cpp snes9x_stub.h /ref/

RUN mkdir -p /ref/apu/bapu/dsp \
    && cp -f /ref/snes9x_stub.h /ref/snes9x.h \
    && cp -f /ref/SPC_DSP.cpp /ref/SPC_DSP.h /ref/blargg_common.h /ref/blargg_config.h \
          /ref/blargg_endian.h /ref/blargg_source.h /ref/apu/bapu/dsp/ \
    && sed -i '1i #include "snes9x_stub.h"' /ref/SPC_DSP.h

RUN g++ -O2 -w -I/ref -I/ref/apu/bapu/dsp -o /ref/sdspref /ref/driver.cpp /ref/apu/bapu/dsp/SPC_DSP.cpp

FROM debian:bookworm-slim

COPY --from=build /ref/sdspref /usr/local/bin/sdspref

RUN useradd --create-home --uid 1000 builder
USER builder
WORKDIR /work

ENTRYPOINT ["sdspref"]
