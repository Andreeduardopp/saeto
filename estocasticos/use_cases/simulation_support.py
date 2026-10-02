"""
Pieces every stochastic-process simulator shares: a seeded generator, the time
grid, figure encoding and summary statistics.
"""
import base64
import io
import secrets

import matplotlib
matplotlib.use('Agg')  # no display on the server
import matplotlib.pyplot as plt
import numpy as np

MAX_SEED = 2 ** 32 - 1


def make_rng(seed=None):
    """A generator and the seed it was built from; no seed draws a new one."""
    if seed is None:
        seed = secrets.randbelow(MAX_SEED + 1)
    return np.random.default_rng(seed), seed


def number_of_steps(T, dt):
    """Increments that fit in [0, T]; the grid then uses dt = T / steps so it ends at T."""
    return max(1, round(T / dt))


def time_grid(T, steps):
    """steps + 1 points from 0 to T, so there are `steps` increments of T / steps."""
    return np.linspace(0, T, steps + 1)


def t(language, pt, en):
    return en if language == 'en' else pt


def encode_figure(fig):
    """PNG as base64, and close the figure so the server does not keep it in memory."""
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', bbox_inches='tight')
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def summary(values):
    """Sample statistics (n - 1) of a 1-D array, as plain floats."""
    values = np.asarray(values, dtype=float)
    ddof = 1 if values.size > 1 else 0
    return {
        'mean': float(np.mean(values)),
        'median': float(np.median(values)),
        'std': float(np.std(values, ddof=ddof)),
        'variance': float(np.var(values, ddof=ddof)),
        'min': float(np.min(values)),
        'max': float(np.max(values)),
        'p5': float(np.percentile(values, 5)),
        'p95': float(np.percentile(values, 95)),
    }
