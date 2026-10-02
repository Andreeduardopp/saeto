import numpy as np
from scipy.stats import lognorm

from estocasticos.use_cases.diffusion_use_case import DiffusionUseCase


class GeometricBrownianMotionUseCase(DiffusionUseCase):
    """
    Geometric Brownian Motion (Samuelson, 1965): dSₜ = μSₜ dt + σSₜ dWₜ,
    discretised by Euler-Maruyama (Itô).

    S_T is log-normal: ln S_T ~ N(ln S₀ + (μ − σ²/2)T, σ²T), so
    E[S_T] = S₀e^{μT} and Var[S_T] = S₀²e^{2μT}(e^{σ²T} − 1).
    """
    paths_title = ('Movimento Browniano Geométrico — trajetórias simuladas', 'Geometric Brownian Motion — simulated paths')
    distribution_title = ('Distribuição dos preços finais S_T', 'Distribution of the final prices S_T')
    value_label = ('Preço Sₜ', 'Price Sₜ')
    mean_path_label = ('Média teórica S₀·e^{μt}', 'Theoretical mean S₀·e^{μt}')
    color = 'green'

    def __init__(self, S0, mu, sigma, T, dt, n_simulations, seed=None, language='pt'):
        self.mu = mu
        self.sigma = sigma
        super().__init__(S0, T, dt, n_simulations, seed, language)

    def increment(self, s, dW):
        return self.mu * s * self.dt + self.sigma * s * dW

    def theoretical_mean(self, time):
        return self.x0 * np.exp(self.mu * time)

    def theoretical_std(self, time):
        return self.x0 * np.exp(self.mu * time) * np.sqrt(np.exp(self.sigma ** 2 * time) - 1)

    def theoretical_pdf(self, x):
        log_mean = np.log(self.x0) + (self.mu - 0.5 * self.sigma ** 2) * self.T
        return lognorm.pdf(x, s=self.sigma * np.sqrt(self.T), scale=np.exp(log_mean))
