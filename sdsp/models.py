"""Which parts this package covers, and what each one is.

The S-DSP is one part with one behaviour. Sony built it into the S-SMP beside
the SPC700 and never sold it separately, so there is no family of revisions to
model. The catalogue exists for the same reason it exists in the sibling
repositories: a hardware difference discovered later should mean adding an entry
rather than restructuring the package around it.
"""


class UnknownModelError(Exception):
    pass


class Model:
    """One part: what it is, what it carries, and how to build it."""

    def __init__(self, name, summary, voices, registers, core, aliases=()):
        self.name = name
        self.summary = summary
        self.voices = voices
        self.registers = registers
        self.core = core
        self.aliases = tuple(aliases)

    def build(self, memory, **options):
        return self.core(self, memory, **options)

    def __repr__(self):
        return f"<Model {self.name}, {self.voices} voices>"


def _build_sdsp(model, memory, **options):
    from .core import Dsp

    dsp = Dsp(memory, **options)
    dsp.model = model.name
    return dsp


_CATALOGUE = (
    Model(
        name="s-dsp",
        summary=(
            "The Sony S-DSP, the wavetable half of the SNES audio unit. Eight voices "
            "reading compressed blocks out of the same sixty four kilobytes the SPC700 "
            "uses, resampled through a gaussian kernel, shaped by envelopes, and mixed "
            "with an echo unit carrying an eight tap filter."
        ),
        voices=8,
        registers=128,
        core=_build_sdsp,
        aliases=("sdsp", "sonysdsp", "dsp", "snesdsp"),
    ),
)

MODELS = {model.name: model for model in _CATALOGUE}

_BY_ALIAS = {}
for _model in _CATALOGUE:
    _BY_ALIAS[_model.name] = _model
    for _alias in _model.aliases:
        _BY_ALIAS[_alias] = _model


def _normalise(name):
    return str(name).strip().lower().replace("-", "").replace("_", "")


def describe(name):
    """The model of that name, however it happens to be written."""
    found = _BY_ALIAS.get(_normalise(name))
    if found is None:
        raise UnknownModelError(
            f"{name} is not a model this package covers; it has {', '.join(sorted(MODELS))}"
        )
    return found
