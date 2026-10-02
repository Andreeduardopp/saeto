import numpy as np
from scipy.stats import norm

from estocasticos.use_cases.diffusion_use_case import DiffusionUseCase


class ArithmeticBrownianMotionUseCase(DiffusionUseCase):
    """
    Arithmetic Brownian Motion: dXₜ = μ dt + σ dWₜ.

    μ and σ are absolute (not proportional to Xₜ), so X_T is normal with
    E[X_T] = X₀ + μT and Var[X_T] = σ²T.
    """
    paths_title = ('Movimento Browniano Aritmético — trajetórias simuladas', 'Arithmetic Brownian Motion — simulated paths')
    distribution_title = ('Distribuição dos valores finais X_T', 'Distribution of the final values X_T')
    value_label = ('Valor Xₜ', 'Value Xₜ')
    mean_path_label = ('Média teórica X₀ + μt', 'Theoretical mean X₀ + μt')

    def __init__(self, X0, mu, sigma, T, dt, n_simulations, seed=None, language='pt'):
        self.mu = mu
        self.sigma = sigma
        super().__init__(X0, T, dt, n_simulations, seed, language)

    def increment(self, x, dW):
        return self.mu * self.dt + self.sigma * dW

    def theoretical_mean(self, time):
        return self.x0 + self.mu * time

    def theoretical_std(self, time):
        return self.sigma * np.sqrt(time)

    def theoretical_pdf(self, x):
        return norm.pdf(x, self.theoretical_mean(self.T), self.theoretical_std(self.T))
