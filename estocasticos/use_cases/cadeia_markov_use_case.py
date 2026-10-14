import matplotlib.pyplot as plt
import numpy as np

from estocasticos.use_cases.simulation_support import encode_figure, t


MAX_MARKOV_STEPS = 100_000
MAX_EVOLUTION_ROWS = 501


def evolution_steps(steps):
    """Bound the displayed/saved table, keeping the actual first and last steps."""
    stride = max(1, (steps + MAX_EVOLUTION_ROWS - 2) // (MAX_EVOLUTION_ROWS - 1))
    return sorted(set(range(0, steps + 1, stride)) | {steps})


class CadeiaMarkovUseCase:
    """
    Evolution of the state distribution of a Markov chain: πₙ₊₁ = πₙ · P.
    Deterministic, so there is no seed.
    """

    def __init__(self, states, transition_matrix, initial_distribution, steps, language='pt'):
        self.states = states
        self.transition_matrix = np.array(transition_matrix, dtype=float)  # rows sum to 1
        # The form accepts rounded percentages. Avoid accumulating their rounding
        # error over long runs (which would make the total probability drift).
        row_totals = self.transition_matrix.sum(axis=1, keepdims=True)
        # A row that adds up to zero has no distribution to normalise: dividing
        # would turn the whole run into NaN behind a numpy warning, so say it here.
        if not np.all(row_totals > 0):
            raise ValueError('each row of the transition matrix must add up to more than zero')
        self.transition_matrix /= row_totals
        self.initial_state = np.array(initial_distribution, dtype=float)
        initial_total = self.initial_state.sum()
        if not initial_total > 0:
            raise ValueError('the initial distribution must add up to more than zero')
        self.initial_state = self.initial_state / initial_total
        self.steps = steps
        self.language = language

    def simulate(self):
        evolution = np.empty((self.steps + 1, len(self.states)))
        evolution[0] = self.initial_state
        for step in range(self.steps):
            evolution[step + 1] = evolution[step] @ self.transition_matrix
        return evolution

    def generate_plot(self, evolution):
        language = self.language
        fig, ax = plt.subplots(figsize=(8, 6))
        iterations = range(len(evolution))
        for i, state in enumerate(self.states):
            # Draw the full trajectory, including oscillations between table rows.
            ax.plot(iterations, evolution[:, i] * 100,
                    marker='o' if self.steps <= 50 else None, label=state)
        ax.set_title(t(language, 'Evolução das probabilidades dos estados', 'Evolution of state probabilities'))
        ax.set_xlabel(t(language, 'Iteração', 'Iteration'))
        ax.set_ylabel(t(language, 'Probabilidade (%)', 'Probability (%)'))
        ax.grid(True, alpha=0.3)
        ax.legend()
        return encode_figure(fig)
