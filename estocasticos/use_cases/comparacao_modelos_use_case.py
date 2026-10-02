import matplotlib.pyplot as plt
import numpy as np

from estocasticos.use_cases.simulation_support import encode_figure, make_rng, number_of_steps, t, time_grid


class ComparacaoModelosUseCase:
    """
    One path of each model on the same time grid, from the same S₀:
    random walk (Xₜ = Xₜ₋₁ + ε, ε ~ N(0, 1) per step), GBM (Euler) and
    mean reversion (Ornstein-Uhlenbeck, Euler).
    """

    def __init__(self, S0, mu_gbm, sigma_gbm, mu_mr, kappa_mr, sigma_mr, T, dt, seed=None, language='pt'):
        self.S0 = S0
        self.mu_gbm = mu_gbm
        self.sigma_gbm = sigma_gbm
        self.mu_mr = mu_mr
        self.kappa_mr = kappa_mr
        self.sigma_mr = sigma_mr
        self.T = T
        self.steps = number_of_steps(T, dt)
        self.dt = T / self.steps
        self.language = language
        self.rng, self.seed = make_rng(seed)
        self.paths = self._simulate()

    def _simulate(self):
        rw_shocks = self.rng.normal(0, 1, self.steps)
        gbm_dW = self.rng.normal(0, np.sqrt(self.dt), self.steps)
        mr_dW = self.rng.normal(0, np.sqrt(self.dt), self.steps)

        random_walk = self.S0 + np.concatenate(([0.0], np.cumsum(rw_shocks)))
        gbm = np.empty(self.steps + 1)
        mean_reversion = np.empty(self.steps + 1)
        gbm[0] = mean_reversion[0] = self.S0
        for i in range(self.steps):
            gbm[i + 1] = gbm[i] + self.mu_gbm * gbm[i] * self.dt + self.sigma_gbm * gbm[i] * gbm_dW[i]
            mean_reversion[i + 1] = (mean_reversion[i] + self.kappa_mr * (self.mu_mr - mean_reversion[i]) * self.dt
                                     + self.sigma_mr * mr_dW[i])
        return {'random_walk': random_walk, 'gbm': gbm, 'mean_reversion': mean_reversion}

    def final_values(self):
        return {name: float(path[-1]) for name, path in self.paths.items()}

    def generate_plot(self):
        language = self.language
        labels = {
            'random_walk': 'Random Walk',
            'gbm': t(language, 'Movimento Browniano Geométrico', 'Geometric Brownian Motion'),
            'mean_reversion': t(language, 'Reversão à Média', 'Mean Reversion'),
        }
        time = time_grid(self.T, self.steps)
        fig, ax = plt.subplots(figsize=(12, 7))
        for name, path in self.paths.items():
            ax.plot(time, path, label=labels[name])
        ax.set_title(t(language, 'Comparação de modelos estocásticos', 'Stochastic models comparison'))
        ax.set_xlabel(t(language, 'Tempo', 'Time'))
        ax.set_ylabel(t(language, 'Valor', 'Value'))
        ax.legend()
        ax.grid(True, alpha=0.3)
        return encode_figure(fig)
