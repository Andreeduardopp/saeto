import matplotlib.pyplot as plt
import numpy as np

from estocasticos.use_cases.simulation_support import encode_figure, make_rng, summary, t

# Shares of the steps the histograms look at: positions from step 0 up to this share.
SHARES = (25, 50, 75, 100)


class RandomWalkNormalUseCase:
    """`paths` walks Xₜ = Xₜ₋₁ + εₜ, ε ~ N(0, 1), X₀ = 0, of `steps` steps each."""

    def __init__(self, steps, paths, seed=None, language='pt'):
        self.steps = steps
        self.paths = paths
        self.language = language
        self.rng, self.seed = make_rng(seed)
        increments = self.rng.normal(0, 1, (paths, steps))
        self.walks = np.hstack((np.zeros((paths, 1)), np.cumsum(increments, axis=1)))

    def _positions(self, share):
        last_step = self.steps * share // 100
        return self.walks[:, :last_step + 1].flatten()

    def statistics(self):
        """Summary of the positions from step 0 to each share of the steps."""
        keys = ('min', 'max', 'mean', 'median', 'variance', 'std')
        return [
            {'share': share, 'stats': {key: value for key, value in summary(self._positions(share)).items() if key in keys}}
            for share in SHARES
        ]

    def plot_walks(self):
        language = self.language
        fig, ax = plt.subplots(figsize=(10, 6))
        for walk in self.walks:
            ax.plot(walk)
        ax.set_title(t(
            language,
            f'Random walk com {self.paths} caminhos e {self.steps} passos',
            f'Random walk with {self.paths} paths and {self.steps} steps',
        ))
        ax.set_xlabel(t(language, 'Passos', 'Steps'))
        ax.set_ylabel(t(language, 'Valor de X', 'X value'))
        ax.grid(True, alpha=0.3)
        return encode_figure(fig)

    def plot_histograms(self):
        language = self.language
        fig, axs = plt.subplots(2, 2, figsize=(12, 10))
        for ax, share in zip(axs.flat, SHARES):
            ax.hist(self._positions(share), bins=30, edgecolor='black')
            ax.set_title(t(language, f'Distribuição: 0% – {share}% dos passos', f'Distribution: 0% – {share}% of the steps'))
            ax.set_xlabel(t(language, 'Valor de X', 'X value'))
            ax.set_ylabel(t(language, 'Frequência', 'Frequency'))
        fig.tight_layout()
        return encode_figure(fig)
