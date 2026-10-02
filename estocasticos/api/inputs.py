"""
Reading and validating the inputs of the stochastic-process calculations.

The limits live here, on the server, so a screen cannot skip them; the error
message comes back in the session language and the screen shows it as is.
"""
import math

from estocasticos.use_cases.simulation_support import MAX_SEED


class InvalidInput(Exception):
    def __init__(self, pt, en):
        super().__init__(pt)
        self.pt = pt
        self.en = en

    def message(self, language):
        return self.en if language == 'en' else self.pt


def _format(value):
    return f'{value:g}'


def read_number(data, name, label, *, minimum=None, maximum=None, integer=False, above=None):
    """
    A number from `data` (a QueryDict or dict). `label` is (pt, en).
    `minimum`/`maximum` are inclusive; `above` is an exclusive lower bound.
    """
    label_pt, label_en = label
    raw = str(data.get(name, '')).strip()
    try:
        value = float(raw)
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or (integer and not value.is_integer()):
        kind_pt, kind_en = ('um número inteiro', 'a whole number') if integer else ('um número', 'a number')
        raise InvalidInput(f'{label_pt}: informe {kind_pt}.', f'{label_en}: enter {kind_en}.')

    if above is not None and value <= above:
        raise InvalidInput(
            f'{label_pt} deve ser maior que {_format(above)}.',
            f'{label_en} must be greater than {_format(above)}.',
        )
    if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        if minimum is not None and maximum is not None:
            raise InvalidInput(
                f'{label_pt} deve estar entre {_format(minimum)} e {_format(maximum)}.',
                f'{label_en} must be between {_format(minimum)} and {_format(maximum)}.',
            )
        if minimum is not None:
            raise InvalidInput(
                f'{label_pt} deve ser no mínimo {_format(minimum)}.',
                f'{label_en} must be at least {_format(minimum)}.',
            )
        raise InvalidInput(
            f'{label_pt} deve ser no máximo {_format(maximum)}.',
            f'{label_en} must be at most {_format(maximum)}.',
        )
    return int(value) if integer else value


def read_seed(data):
    """The optional seed: None when empty, so the simulator draws one."""
    if str(data.get('seed', '')).strip() == '':
        return None
    return read_number(data, 'seed', ('Semente', 'Seed'), minimum=0, maximum=MAX_SEED, integer=True)


def read_choice(data, name, label, choices):
    value = data.get(name)
    if value not in choices:
        raise InvalidInput(f'{label[0]}: opção inválida.', f'{label[1]}: invalid option.')
    return value


def check_grid(steps, simulations, *, max_steps=10000, max_cells=2_000_000):
    """Keeps a run small enough to answer quickly: T / dt steps × simulations."""
    if steps > max_steps:
        raise InvalidInput(
            f'T / dt dá {steps} passos; o máximo é {max_steps}. Aumente o passo de tempo ou reduza o horizonte.',
            f'T / dt gives {steps} steps; the maximum is {max_steps}. Increase the time step or shorten the horizon.',
        )
    if steps * simulations > max_cells:
        raise InvalidInput(
            f'Passos × simulações = {steps * simulations:,}; o máximo é {max_cells:,}. Reduza um dos dois.'.replace(',', '.'),
            f'Steps × simulations = {steps * simulations:,}; the maximum is {max_cells:,}. Reduce one of them.',
        )
