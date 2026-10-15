import random

# The strategies the screen offers and the view accepts.
STRATEGIES = ('always_cooperate', 'always_defect', 'tit_for_tat', 'random')

# One round is a pair of moves and a pair of scores, so the cost grows with the
# number of rounds alone. A thousand rounds answer immediately and already show
# every pattern these four strategies produce; the screen reads the history one
# page at a time instead of rendering every round at once.
MIN_ITERATIONS = 1
MAX_ITERATIONS = 1000
DEFAULT_ITERATIONS = 10
HISTORY_PAGE_SIZE = 50

COOPERATE = 'cooperate'
DEFECT = 'defect'

# Scores are whole points: (move of player 1, move of player 2) -> (score 1, score 2).
PAYOFFS = {
    (COOPERATE, COOPERATE): (3, 3),
    (COOPERATE, DEFECT): (0, 5),
    (DEFECT, COOPERATE): (5, 0),
    (DEFECT, DEFECT): (1, 1),
}


class DilemaPrisioneiroUseCase:
    def __init__(self, strategy1, strategy2, iterations):
        self.strategy1 = strategy1
        self.strategy2 = strategy2
        self.iterations = iterations
        self.history1 = []
        self.history2 = []
        self.payoff1 = 0
        self.payoff2 = 0

    def get_payoffs(self, move1, move2):
        return PAYOFFS[(move1, move2)]

    def get_move(self, strategy, history, opponent_history):
        if strategy == 'always_cooperate':
            return COOPERATE
        if strategy == 'always_defect':
            return DEFECT
        if strategy == 'tit_for_tat':
            # It opens by cooperating and then repeats the opponent's last move.
            return opponent_history[-1] if opponent_history else COOPERATE
        if strategy == 'random':
            return random.choice([COOPERATE, DEFECT])
        raise ValueError(f'Unknown strategy: {strategy}')

    def run_simulation(self):
        for _ in range(self.iterations):
            move1 = self.get_move(self.strategy1, self.history1, self.history2)
            move2 = self.get_move(self.strategy2, self.history2, self.history1)

            self.history1.append(move1)
            self.history2.append(move2)

            payoff1, payoff2 = self.get_payoffs(move1, move2)
            self.payoff1 += payoff1
            self.payoff2 += payoff2

        return {
            'history1': self.history1,
            'history2': self.history2,
            'payoff1': self.payoff1,
            'payoff2': self.payoff2,
        }
