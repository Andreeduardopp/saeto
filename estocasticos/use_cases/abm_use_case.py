import numpy as np
import matplotlib.pyplot as plt
import io
import base64


class ArithmeticBrownianMotionUseCase:
    """
    Arithmetic Brownian Motion (ABM) simulation.

    Defined by the SDE:
        dX_t = mu * dt + sigma * dW_t

    Unlike GBM, drift (mu) and volatility (sigma) are absolute constants —
    not proportional to the current value. This yields a normal distribution
    for X_t at any time t, with:
        E[X_t]   = X_0 + mu * t
        Var[X_t] = sigma^2 * t
    """

    def __init__(self, X0: float, mu: float, sigma: float, T: float, dt: float, n_simulations: int):
        self.X0 = X0
        self.mu = mu
        self.sigma = sigma
        self.T = T
        self.dt = dt
        self.n_simulations = n_simulations

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def simulate_paths(self):
        n_steps = int(self.T / self.dt)
        time_grid = np.linspace(0, self.T, n_steps)

        simulations = np.zeros((self.n_simulations, n_steps))
        simulations[:, 0] = self.X0

        sqrt_dt = np.sqrt(self.dt)
        for i in range(1, n_steps):
            dW = np.random.normal(0, sqrt_dt, size=self.n_simulations)
            simulations[:, i] = simulations[:, i - 1] + self.mu * self.dt + self.sigma * dW

        return time_grid, simulations

    # ------------------------------------------------------------------
    # Plots
    # ------------------------------------------------------------------

    def _encode_figure(self, fig) -> str:
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", bbox_inches="tight")
        buffer.seek(0)
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        buffer.close()
        plt.close(fig)
        return encoded

    def plot_paths(self, time_grid, simulations) -> str:
        fig, ax = plt.subplots(figsize=(10, 6))

        for sim in simulations:
            ax.plot(time_grid, sim, lw=0.8, alpha=0.55)

        # Theoretical mean path
        mean_path = self.X0 + self.mu * time_grid
        ax.plot(time_grid, mean_path, "k--", lw=2, label=f"Mean path: $X_0 + \\mu t$")

        ax.set_title("Arithmetic Brownian Motion — Simulated Paths")
        ax.set_xlabel("Time (t)")
        ax.set_ylabel("Value $X_t$")
        ax.legend()
        ax.grid(alpha=0.3)

        return self._encode_figure(fig)

    def plot_distribution(self, simulations) -> str:
        final_values = simulations[:, -1]

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(final_values, bins=30, alpha=0.7, color="steelblue", edgecolor="white")

        # Overlay theoretical normal distribution
        from scipy.stats import norm
        mean_theory = self.X0 + self.mu * self.T
        std_theory = self.sigma * np.sqrt(self.T)
        x_range = np.linspace(final_values.min(), final_values.max(), 300)
        pdf_scaled = norm.pdf(x_range, mean_theory, std_theory) * len(final_values) * (
            (final_values.max() - final_values.min()) / 30
        )
        ax.plot(x_range, pdf_scaled, "r-", lw=2, label=f"Theoretical $\\mathcal{{N}}({mean_theory:.2f}, {std_theory:.2f}^2)$")

        ax.set_title("Distribution of Final Values $X_T$")
        ax.set_xlabel("Final Value")
        ax.set_ylabel("Frequency")
        ax.legend()
        ax.grid(alpha=0.3)

        return self._encode_figure(fig)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def calculate_statistics(self, simulations) -> dict:
        final_values = simulations[:, -1]
        mean_theory = self.X0 + self.mu * self.T
        std_theory = self.sigma * np.sqrt(self.T)

        return {
            "Mean (simulated)": float(np.mean(final_values)),
            "Mean (theoretical)": float(mean_theory),
            "Std Dev (simulated)": float(np.std(final_values)),
            "Std Dev (theoretical)": float(std_theory),
            "Variance (simulated)": float(np.var(final_values)),
            "Variance (theoretical)": float(std_theory ** 2),
            "Min": float(np.min(final_values)),
            "Max": float(np.max(final_values)),
            "5th Percentile": float(np.percentile(final_values, 5)),
            "95th Percentile": float(np.percentile(final_values, 95)),
        }
