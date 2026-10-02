"""
Base for the one-factor diffusions simulated by Euler-Maruyama (ABM, GBM, mean
reversion): the paths, the two charts and the statistics of the final value
against the model's exact moments.
"""
import matplotlib.pyplot as plt
import numpy as np

from estocasticos.use_cases.simulation_support import (
    encode_figure, make_rng, number_of_steps, summary, t, time_grid,
)

# Drawing more lines only slows the chart down; the statistics use every path.
MAX_PLOTTED_PATHS = 200


class DiffusionUseCase:
    # (pt, en) texts, set by each model
    paths_title = ('', '')
    distribution_title = ('', '')
    value_label = ('Valor', 'Value')
    mean_path_label = ('Média teórica', 'Theoretical mean')
    color = 'steelblue'

    def __init__(self, x0, T, dt, n_simulations, seed=None, language='pt'):
        self.x0 = x0
        self.T = T
        self.steps = number_of_steps(T, dt)
        self.dt = T / self.steps  # ends the grid exactly at T
        self.time = time_grid(T, self.steps)
        self.n_simulations = n_simulations
        self.language = language
        self.rng, self.seed = make_rng(seed)
        self.paths = self._simulate()

    # --- model -------------------------------------------------------------

    def increment(self, x, dW):
        raise NotImplementedError

    def theoretical_mean(self, time):
        raise NotImplementedError

    def theoretical_std(self, time):
        raise NotImplementedError

    def theoretical_pdf(self, x):
        """Density of the final value X_T."""
        raise NotImplementedError

    # --- simulation --------------------------------------------------------

    def _simulate(self):
        paths = np.empty((self.n_simulations, self.steps + 1))
        paths[:, 0] = self.x0
        dW = self.rng.normal(0, np.sqrt(self.dt), (self.n_simulations, self.steps))
        for i in range(self.steps):
            paths[:, i + 1] = paths[:, i] + self.increment(paths[:, i], dW[:, i])
        return paths

    @property
    def final_values(self):
        return self.paths[:, -1]

    def statistics(self):
        simulated = summary(self.final_values)
        std_theory = float(self.theoretical_std(self.T))
        return {
            'mean': simulated['mean'],
            'mean_theoretical': float(self.theoretical_mean(self.T)),
            'std': simulated['std'],
            'std_theoretical': std_theory,
            'variance': simulated['variance'],
            'variance_theoretical': std_theory ** 2,
            'min': simulated['min'],
            'max': simulated['max'],
            'p5': simulated['p5'],
            'p95': simulated['p95'],
        }

    # --- charts ------------------------------------------------------------

    def _t(self, texts):
        return t(self.language, *texts)

    def plot_paths(self):
        fig, ax = plt.subplots(figsize=(10, 6))
        for path in self.paths[:MAX_PLOTTED_PATHS]:
            ax.plot(self.time, path, lw=0.8, alpha=0.55)
        ax.plot(self.time, self.theoretical_mean(self.time), 'k--', lw=2, label=self._t(self.mean_path_label))
        ax.set_title(self._t(self.paths_title))
        ax.set_xlabel(self._t(('Tempo (t)', 'Time (t)')))
        ax.set_ylabel(self._t(self.value_label))
        ax.legend()
        ax.grid(alpha=0.3)
        return encode_figure(fig)

    def plot_distribution(self, bins=30):
        final = self.final_values
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(final, bins=bins, alpha=0.7, color=self.color, edgecolor='white')
        if final.max() > final.min():
            x = np.linspace(final.min(), final.max(), 300)
            bin_width = (final.max() - final.min()) / bins
            ax.plot(x, self.theoretical_pdf(x) * final.size * bin_width, 'r-', lw=2,
                    label=self._t(('Distribuição teórica', 'Theoretical distribution')))
            ax.legend()
        ax.set_title(self._t(self.distribution_title))
        ax.set_xlabel(self._t(('Valor final', 'Final value')))
        ax.set_ylabel(self._t(('Frequência', 'Frequency')))
        ax.grid(alpha=0.3)
        return encode_figure(fig)
