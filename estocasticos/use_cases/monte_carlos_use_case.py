import matplotlib.pyplot as plt
import numpy as np

from estocasticos.use_cases.simulation_support import encode_figure, make_rng, t

# Length of one period in years, by the time unit the screen offers.
PERIOD_IN_YEARS = {'Dia': 1 / 252, 'Semana': 1 / 52, 'Mês': 1 / 12, 'Ano': 1.0}
TIME_UNIT_LABELS = {
    'pt': {'Dia': 'Dias', 'Semana': 'Semanas', 'Mês': 'Meses', 'Ano': 'Anos'},
    'en': {'Dia': 'Days', 'Semana': 'Weeks', 'Mês': 'Months', 'Ano': 'Years'},
}
MAX_PLOTTED_PATHS = 100
STYLE = 'seaborn-v0_8-darkgrid'


class MonteCarloUseCase:
    """
    GBM paths by the exact solution Sₜ = S₀·exp((μ − σ²/2)t + σWₜ), with μ and σ
    annual and one step per period of the chosen time unit.
    """

    def __init__(self, S0, mu, sigma, time_unit, num_periods, num_simulations, seed=None, language='pt'):
        self.S0 = float(S0)
        self.mu = float(mu)
        self.sigma = float(sigma)
        self.time_unit = time_unit
        self.num_periods = int(num_periods)
        self.num_simulations = int(num_simulations)
        self.language = language
        self.rng, self.seed = make_rng(seed)
        self.prices = None

    def run_simulation(self):
        dt = PERIOD_IN_YEARS[self.time_unit]
        z = self.rng.normal(0, 1, (self.num_simulations, self.num_periods))
        log_returns = np.cumsum((self.mu - 0.5 * self.sigma ** 2) * dt + self.sigma * np.sqrt(dt) * z, axis=1)
        log_returns = np.hstack((np.zeros((self.num_simulations, 1)), log_returns))  # t = 0
        self.prices = self.S0 * np.exp(log_returns)
        return self.prices

    @property
    def final_prices(self):
        return self.prices[:, -1]

    def _unit(self):
        return TIME_UNIT_LABELS['en' if self.language == 'en' else 'pt'][self.time_unit]

    def plot_simulation(self):
        language = self.language
        with plt.style.context(STYLE):
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.plot(self.prices[:MAX_PLOTTED_PATHS].T, lw=1, alpha=0.5)
            ax.set_title(t(language, 'Evolução dos preços (simulação de Monte Carlo)', 'Price paths (Monte Carlo simulation)'))
            ax.set_xlabel(t(language, f'Períodos ({self._unit()})', f'Periods ({self._unit()})'))
            ax.set_ylabel(t(language, 'Preço do ativo', 'Asset price'))
            return encode_figure(fig)

    def get_final_price_distribution(self):
        language = self.language
        mean_price = float(np.mean(self.final_prices))
        with plt.style.context(STYLE):
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.hist(self.final_prices, bins=50, alpha=0.75, color='steelblue', edgecolor='white')
            ax.axvline(mean_price, color='firebrick', linestyle='--', label=t(language, f'Média: {mean_price:.2f}', f'Mean: {mean_price:.2f}'))
            ax.set_title(t(language, 'Distribuição dos preços finais', 'Distribution of the final prices'))
            ax.set_xlabel(t(language, 'Preço do ativo', 'Asset price'))
            ax.set_ylabel(t(language, 'Frequência', 'Frequency'))
            ax.legend()
            return encode_figure(fig)

    def plot_convergence(self):
        """Running mean of the final prices with its 95% confidence band."""
        language = self.language
        final = self.final_prices
        n = np.arange(1, final.size + 1)
        running_mean = np.cumsum(final) / n
        running_var = np.maximum(np.cumsum(final ** 2) / n - running_mean ** 2, 0)
        half_width = 1.96 * np.sqrt(running_var) / np.sqrt(n)
        with plt.style.context(STYLE):
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.plot(n, running_mean, color='#333333', lw=1.5, label=t(language, 'Preço médio estimado', 'Estimated mean price'))
            ax.fill_between(n, running_mean - half_width, running_mean + half_width, color='gray', alpha=0.3,
                            label=t(language, 'IC 95%', '95% CI'))
            ax.axhline(running_mean[-1], color='firebrick', linestyle='--', alpha=0.8,
                       label=t(language, f'Final: {running_mean[-1]:.2f}', f'Final: {running_mean[-1]:.2f}'))
            ax.set_title(t(language, 'Convergência da média dos preços finais', 'Convergence of the mean final price'))
            ax.set_xlabel(t(language, 'Número de simulações', 'Number of simulations'))
            ax.set_ylabel(t(language, 'Preço médio', 'Mean price'))
            ax.legend()
            return encode_figure(fig)

    def get_statistics(self):
        final = self.final_prices
        mean = float(np.mean(final))
        std = float(np.std(final, ddof=1))
        standard_error = std / np.sqrt(final.size)
        return {
            'descriptive': {
                'mean': mean,
                'std': std,
                'min': float(np.min(final)),
                'max': float(np.max(final)),
                'expected_return': (mean / self.S0 - 1) * 100,
            },
            'inferential': {
                'mean': mean,
                'standard_error': float(standard_error),
                'ci_lower': float(mean - 1.96 * standard_error),
                'ci_upper': float(mean + 1.96 * standard_error),
            },
        }
