import matplotlib.pyplot as plt
import numpy as np

from estocasticos.use_cases.simulation_support import encode_figure, t


class CadeiaMarkovUseCase:
    """
    Evolution of the state distribution of a Markov chain: πₙ₊₁ = πₙ · P.
    Deterministic, so there is no seed.
    """

    def __init__(self, states, transition_matrix, initial_distribution, steps, language='pt'):
        self.states = states
        self.transition_matrix = np.array(transition_matrix, dtype=float)  # rows sum to 1
        self.initial_state = np.array(initial_distribution, dtype=float)
        self.initial_state = self.initial_state / self.initial_state.sum()
        self.steps = steps
        self.language = language

    def simulate(self):
        evolution = [self.initial_state]
        for _ in range(self.steps):
            evolution.append(evolution[-1] @ self.transition_matrix)
        return [state.tolist() for state in evolution]

    def generate_plot(self, evolution):
        language = self.language
        fig, ax = plt.subplots(figsize=(8, 6))
        iterations = range(len(evolution))
        for i, state in enumerate(self.states):
            ax.plot(iterations, [vector[i] * 100 for vector in evolution], marker='o', label=state)
        ax.set_title(t(language, 'Evolução das probabilidades dos estados', 'Evolution of state probabilities'))
        ax.set_xlabel(t(language, 'Iteração', 'Iteration'))
        ax.set_ylabel(t(language, 'Probabilidade (%)', 'Probability (%)'))
        ax.grid(True, alpha=0.3)
        ax.legend()
        return encode_figure(fig)
