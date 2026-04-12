import numpy as np
import matplotlib.pyplot as plt
import io
import base64


class GeometricBrownianMotionUseCase:
    """
    Geometric Brownian Motion (GBM) simulation — Samuelson (1965).

    Defined by the SDE:
        dS_t = mu * S_t * dt + sigma * S_t * dW_t

    Unlike ABM, drift (mu) and volatility (sigma) are proportional to
    the current price S_t.  This yields a **log-normal** distribution
    for S_t at any time t, with:
        E[S_t]   = S_0 * exp(mu * t)
        Var[S_t] = S_0^2 * exp(2*mu*t) * (exp(sigma^2 * t) - 1)

    GBM guarantees non-negative prices (limited liability).
    """

    def __init__(self, S0, mu, sigma, T, dt, n_simulations):
        self.S0 = S0
        self.mu = mu
        self.sigma = sigma
        self.T = T
        self.dt = dt
        self.n_simulations = n_simulations

    # ------------------------------------------------------------------
    # Simulation  (Euler-Maruyama discretisation)
    # ------------------------------------------------------------------

    def simulate_paths(self):
        n_steps = int(self.T / self.dt)
        time_grid = np.linspace(0, self.T, n_steps)

        simulations = np.zeros((self.n_simulations, n_steps))
        simulations[:, 0] = self.S0

        sqrt_dt = np.sqrt(self.dt)
        for i in range(1, n_steps):
            Z = np.random.normal(size=self.n_simulations)
            dW = Z * sqrt_dt
            dS = (
                self.mu * simulations[:, i - 1] * self.dt
                + self.sigma * simulations[:, i - 1] * dW
            )
            simulations[:, i] = simulations[:, i - 1] + dS

        return time_grid, simulations

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _encode_figure(self, fig) -> str:
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", bbox_inches="tight")
        buffer.seek(0)
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        buffer.close()
        plt.close(fig)
        return encoded

    # ------------------------------------------------------------------
    # Plots
    # ------------------------------------------------------------------

    def plot_paths(self, time_grid, simulations):
        fig, ax = plt.subplots(figsize=(10, 6))

        for sim in simulations:
            ax.plot(time_grid, sim, lw=0.8, alpha=0.55)

        # Theoretical mean path: E[S_t] = S_0 * exp(mu * t)
        mean_path = self.S0 * np.exp(self.mu * time_grid)
        ax.plot(time_grid, mean_path, "k--", lw=2,
                label=r"Mean path: $S_0 \cdot e^{\mu t}$")

        ax.set_title("Geometric Brownian Motion — Simulated Paths")
        ax.set_xlabel("Time (t)")
        ax.set_ylabel("Price $S_t$")
        ax.legend()
        ax.grid(alpha=0.3)

        return self._encode_figure(fig)

    def plot_distribution(self, simulations):
        final_prices = simulations[:, -1]

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(final_prices, bins=30, alpha=0.7, color="green",
                edgecolor="white", density=False)

        # Overlay theoretical log-normal distribution
        from scipy.stats import lognorm

        # GBM exact: ln(S_T) ~ N(ln(S_0) + (mu - sigma^2/2)*T , sigma^2*T)
        log_mean = np.log(self.S0) + (self.mu - 0.5 * self.sigma ** 2) * self.T
        log_std = self.sigma * np.sqrt(self.T)

        x_range = np.linspace(
            max(final_prices.min() * 0.8, 1e-6),
            final_prices.max() * 1.2,
            300,
        )

        # scipy lognorm: shape=s, scale=exp(mu_log)
        pdf_values = lognorm.pdf(x_range, s=log_std, scale=np.exp(log_mean))
        # Scale PDF to histogram counts
        bin_width = (final_prices.max() - final_prices.min()) / 30
        pdf_scaled = pdf_values * len(final_prices) * bin_width
        ax.plot(x_range, pdf_scaled, "r-", lw=2,
                label=f"Theoretical LogNormal")

        ax.set_title("Distribution of Final Prices $S_T$")
        ax.set_xlabel("Final Price")
        ax.set_ylabel("Frequency")
        ax.legend()
        ax.grid(alpha=0.3)

        return self._encode_figure(fig)

    # ------------------------------------------------------------------
    # Statistics  (simulated + theoretical)
    # ------------------------------------------------------------------

    def calculate_statistics(self, simulations):
        final_prices = simulations[:, -1]

        # Theoretical moments for GBM
        mean_theory = self.S0 * np.exp(self.mu * self.T)
        var_theory = (self.S0 ** 2) * np.exp(2 * self.mu * self.T) * (
            np.exp(self.sigma ** 2 * self.T) - 1
        )
        std_theory = np.sqrt(var_theory)

        return {
            "Mean (simulated)": float(np.mean(final_prices)),
            "Mean (theoretical)": float(mean_theory),
            "Std Dev (simulated)": float(np.std(final_prices)),
            "Std Dev (theoretical)": float(std_theory),
            "Variance (simulated)": float(np.var(final_prices)),
            "Variance (theoretical)": float(var_theory),
            "Min": float(np.min(final_prices)),
            "Max": float(np.max(final_prices)),
            "5th Percentile": float(np.percentile(final_prices, 5)),
            "95th Percentile": float(np.percentile(final_prices, 95)),
        }
