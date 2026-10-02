import matplotlib.pyplot as plt
import numpy as np

from estocasticos.use_cases.simulation_support import encode_figure, make_rng, t

# Standard deviation of one step of each distribution.
STEP_STD = {
    'normal': 1.0,              # N(0, 1)
    'uniform': 1 / np.sqrt(3),  # U(-1, 1)
    'discrete': 1.0,            # ±1 with probability 1/2
}


class RandomWalkUseCase:
    """Xₜ = Xₜ₋₁ + εₜ from X₀ = 0, for three distributions of ε."""

    def __init__(self, steps, seed=None, language='pt'):
        self.steps = steps
        self.language = language
        self.rng, self.seed = make_rng(seed)
        self.walks = {name: self._walk(name) for name in STEP_STD}

    def _walk(self, distribution):
        if distribution == 'normal':
            epsilon = self.rng.normal(0, 1, self.steps)
        elif distribution == 'uniform':
            epsilon = self.rng.uniform(-1, 1, self.steps)
        else:
            epsilon = self.rng.choice([-1, 1], self.steps)
        return np.concatenate(([0.0], np.cumsum(epsilon)))  # steps + 1 points

    def statistics(self):
        """Per distribution: final value, extremes and the theoretical std of the final value (σ√n)."""
        return {
            name: {
                'final': float(walk[-1]),
                'min': float(walk.min()),
                'max': float(walk.max()),
                'std_theoretical': float(STEP_STD[name] * np.sqrt(self.steps)),
            }
            for name, walk in self.walks.items()
        }

    def generate_plot(self):
        language = self.language
        labels = {
            'normal': t(language, 'Distribuição normal N(0, 1)', 'Normal distribution N(0, 1)'),
            'uniform': t(language, 'Distribuição uniforme U(−1, 1)', 'Uniform distribution U(−1, 1)'),
            'discrete': t(language, 'Distribuição discreta {−1, 1}', 'Discrete distribution {−1, 1}'),
        }
        fig, ax = plt.subplots(figsize=(10, 6))
        for name, walk in self.walks.items():
            ax.plot(walk, label=labels[name])
        ax.set_title(t(language, 'Random walk com diferentes distribuições', 'Random walk with different distributions'))
        ax.set_xlabel(t(language, 'Passos', 'Steps'))
        ax.set_ylabel(t(language, 'Valor de X', 'X value'))
        ax.legend()
        ax.grid(True, alpha=0.3)
        return encode_figure(fig)
