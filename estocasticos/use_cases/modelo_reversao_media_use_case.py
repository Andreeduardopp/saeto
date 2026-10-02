import numpy as np
from scipy.stats import norm

from estocasticos.use_cases.diffusion_use_case import DiffusionUseCase


class ReversaoMediaUseCase(DiffusionUseCase):
    """
    Mean reversion (Ornstein-Uhlenbeck): dXₜ = κ(μ − Xₜ) dt + σ dWₜ.

    X_T is normal with E[X_T] = μ + (X₀ − μ)e^{−κT} and
    Var[X_T] = σ²(1 − e^{−2κT}) / (2κ).
    """
    paths_title = ('Reversão à média — trajetórias simuladas', 'Mean reversion — simulated paths')
    distribution_title = ('Distribuição dos valores finais X_T', 'Distribution of the final values X_T')
    value_label = ('Valor Xₜ', 'Value Xₜ')
    mean_path_label = ('Média teórica μ + (X₀ − μ)e^{−κt}', 'Theoretical mean μ + (X₀ − μ)e^{−κt}')
    color = 'green'

    def __init__(self, S0, mu, kappa, sigma, T, dt, n_simulations, seed=None, language='pt'):
        self.mu = mu
        self.kappa = kappa
        self.sigma = sigma
        super().__init__(S0, T, dt, n_simulations, seed, language)

    def increment(self, x, dW):
        return self.kappa * (self.mu - x) * self.dt + self.sigma * dW

    def theoretical_mean(self, time):
        return self.mu + (self.x0 - self.mu) * np.exp(-self.kappa * time)

    def theoretical_std(self, time):
        return self.sigma * np.sqrt((1 - np.exp(-2 * self.kappa * time)) / (2 * self.kappa))

    def theoretical_pdf(self, x):
        return norm.pdf(x, self.theoretical_mean(self.T), self.theoretical_std(self.T))
