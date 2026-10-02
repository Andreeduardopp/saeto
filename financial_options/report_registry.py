"""
Single source of truth for every financial model that can be saved.

Each ``model_type`` maps to a ``ModelSpec``, which the save, report, rerun and
list code all read from. To add a model: add the choice, add an entry here and
the coverage test in ``financial_options/tests.py`` passes again.
"""
from dataclasses import dataclass, field
from typing import Callable

from estocasticos.labels import stat_label
from financial_options.models import FinantialModelsChoices


# Context keys a report renders with |safe, so the view sanitizes them first.
REPORT_HTML_FIELDS = ('interpretation', 'latticeContainer')


@dataclass(frozen=True)
class ModelSpec:
    template: str                                     # screen to re-run on
    build_report: Callable[[dict, dict, str], dict]   # (parameters, results, language) -> context
    defaults: dict = field(default_factory=dict)      # initial_data for first load and rerun
    param_labels: dict = field(default_factory=dict)  # {'pt': {key: label}, 'en': {...}}
    value_labels: dict = field(default_factory=dict)  # {'pt': {key: {value: label}}, 'en': {...}}
    table_params: tuple = ()                          # list inputs the report shows in a table instead

    def label_parameters(self, parameters, language):
        """Translate parameter names and choice values, in the order of ``param_labels``."""
        names = self.param_labels.get(language) or self.param_labels.get('pt', {})
        values = self.value_labels.get(language) or self.value_labels.get('pt', {})
        ordered_keys = [key for key in names if key in parameters]
        ordered_keys += [key for key in parameters if key not in names]
        ordered_keys = [key for key in ordered_keys if key not in self.table_params]

        labelled = {}
        for key in ordered_keys:
            value = parameters[key]
            if isinstance(value, str):
                value = values.get(key, {}).get(value, value)
            labelled[names.get(key, key)] = value
        return labelled


# --- Formatting helpers ------------------------------------------------------

def _t(language, pt, en):
    return en if language == 'en' else pt


def _number(value, language, decimals=2, prefix=''):
    try:
        number = round(float(value), decimals)
    except (TypeError, ValueError):
        return '-'
    sign = '-' if number < 0 else ''
    text = f'{abs(number):,.{decimals}f}'
    if language != 'en':
        text = text.translate(str.maketrans(',.', '.,'))
    return f'{sign}{prefix}{text}'


def _money(value, language):
    return _number(value, language, prefix='R$ ')


def _percent(value, language):
    text = _number(value, language)
    return text if text == '-' else f'{text}%'


def _charts(charts):
    return {title: image for title, image in charts.items() if image}


def _money_table(title, headers, rows, language):
    return {
        'title': title,
        'headers': headers,
        'rows': [[_money(cell, language) for cell in row] for row in rows or []],
    }


def _probability_percent(value):
    try:
        return round(float(value) * 100, 1)
    except (TypeError, ValueError):
        return '-'


# --- Older screens: the results are the display strings the screen showed ----

def _greeks_title(language):
    return _t(language, 'Gregas (Medidas de Sensibilidade)', 'Greeks (Sensitivity Measures)')


def build_black_scholes_report(parameters, results, language):
    return {
        'results': {
            _t(language, 'Valor da Opção', 'Option Value'): results.get('option_price'),
            'd1': results.get('d1'),
            'd2': results.get('d2'),
            'N(d1)': results.get('n_d1'),
            'N(d2)': results.get('n_d2'),
            _t(language, 'Ponto de Equilíbrio', 'Break-Even Point'): results.get('break_even'),
            _t(language, 'Perda Máxima', 'Maximum Loss'): results.get('max_loss'),
        },
        'nested_results': {_greeks_title(language): results.get('greeks', {})},
        'interpretation': results.get('interpretation'),
        'charts': _charts({
            _t(language, 'Lucro/Prejuízo no Vencimento', 'Profit/Loss at Expiration'): results.get('payoff_plot'),
        }),
    }


def build_cox_ross_report(parameters, results, language):
    return {
        'results': {
            _t(language, 'Valor da Opção', 'Option Value'): results.get('option_price'),
            _t(language, 'Fator de alta (u)', 'Up factor (u)'): results.get('upFactor'),
            _t(language, 'Fator de baixa (d)', 'Down factor (d)'): results.get('downFactor'),
            _t(language, 'Probabilidade neutra ao risco (%)', 'Risk-neutral probability (%)'): _probability_percent(results.get('prob')),
            _t(language, 'Passo de tempo (anos)', 'Time step (years)'): results.get('dt', '-'),
            _t(language, 'Ponto de Equilíbrio', 'Break-Even Point'): results.get('break_even'),
            _t(language, 'Perda Máxima', 'Maximum Loss'): results.get('max_loss'),
            _t(language, 'VPL tradicional (sem flexibilidade)', 'Traditional NPV (without flexibility)'): results.get('traditionalNPV'),
            _t(language, 'VPL expandido (com valor da opção)', 'Expanded NPV (with option value)'): results.get('expandedNPV'),
            _t(language, 'Valor da flexibilidade', 'Value of flexibility'): results.get('flexibilityValue', '-'),
            _t(language, 'Razão valor da opção / custo de investimento', 'Option value / investment cost ratio'): results.get('optionRatio'),
        },
        'nested_results': {_greeks_title(language): results.get('greeks', {})},
        'interpretation': results.get('interpretation'),
        'latticeContainer': results.get('lattice'),
    }


def build_monte_carlo_european_report(parameters, results, language):
    return {
        'results': {_t(language, 'Preço Estimado da Opção', 'Estimated Option Price'): results.get('estimated_price')},
        # The statistic names are the ones the screen showed, in the language it was in.
        'nested_results': {
            _t(language, 'Estatísticas Descritivas (Ativo ST)', 'Descriptive Statistics (Asset Price ST)'): results.get('statistics', {}),
        },
        'charts': _charts({
            _t(language, 'Convergência do Preço Médio', 'Mean Price Convergence'): results.get('price_plot'),
            _t(language, 'Distribuição de Preços Finais', 'Final Price Distribution'): results.get('distribution_plot'),
        }),
        'interpretation': results.get('interpretation'),
    }


def build_monte_carlo_american_report(parameters, results, language):
    return {
        'results': {_t(language, 'Preço Estimado da Opção', 'Estimated Option Price'): results.get('preco_estimado')},
        'nested_results': {},
        'charts': _charts({
            _t(language, 'Trajetórias de Preço Simuladas', 'Simulated Price Paths'): results.get('price_plot'),
            _t(language, 'Fronteira Ótima de Exercício', 'Optimal Exercise Boundary'): results.get('exercise_boundary_plot'),
            _t(language, 'Convergência do Preço da Opção', 'Option Price Convergence'): results.get('convergence_plot'),
        }),
        'interpretation': results.get('interpretation'),
    }


# Black-Scholes, BSM, GBSM and CRR share input ids; each model only has some of them.
# The order is the order of the inputs on the screens.
BLACK_SCHOLES_PARAM_LABELS = {
    'pt': {
        'option_type': 'Tipo de Opção', 'asset_price': 'Preço do Ativo Subjacente (S)',
        'exercise_price': 'Preço de Exercício (K)', 'time_to_expiration': 'Tempo até o Vencimento (dias)',
        'interest_rate': 'Taxa de Juros Livre de Risco (r, %)', 'volatility': 'Volatilidade (σ, %)',
        'dividend_yield': 'Rendimento de Dividendos (q, %)', 'cost_of_carry': 'Custo de Carregamento (b, %)',
        'steps': 'Número de Passos',
    },
    'en': {
        'option_type': 'Option Type', 'asset_price': 'Underlying Asset Price (S)',
        'exercise_price': 'Strike Price (K)', 'time_to_expiration': 'Time to Expiration (days)',
        'interest_rate': 'Risk-Free Interest Rate (r, %)', 'volatility': 'Volatility (σ, %)',
        'dividend_yield': 'Dividend Yield (q, %)', 'cost_of_carry': 'Cost of Carry (b, %)',
        'steps': 'Number of Steps',
    },
}


MONTE_CARLO_PARAM_LABELS = {
    'en': {
        'S0': 'Initial Price (S0)', 'K': 'Strike Price (K)', 'T': 'Time to Maturity (T in years)',
        'r': 'Risk-Free Rate (r, %)', 'sigma': 'Volatility (σ, %)', 'num_simulacoes': 'Number of Simulations',
        'option_type': 'Option Type', 'num_passos': 'Number of Time Steps',
    },
    'pt': {
        'S0': 'Preço Atual do Ativo (S0)', 'K': 'Preço de Exercício (K)', 'T': 'Tempo até o Vencimento (T em anos)',
        'r': 'Taxa de Juros Livre de Risco (r, %)', 'sigma': 'Volatilidade (σ, %)', 'num_simulacoes': 'Número de Simulações',
        'option_type': 'Tipo de Opção', 'num_passos': 'Número de Passos de Tempo',
    },
}


# --- Finite Difference European ----------------------------------------------

def build_fdm_european_report(parameters, results, language):
    greeks = results.get('greeks') or {}
    return {
        'results': {
            _t(language, 'Preço MDF', 'FDM price'): _number(results.get('option_price'), language, 4),
            _t(language, 'Preço Black-Scholes (exato)', 'Black-Scholes price (exact)'): _number(results.get('bs_price'), language, 4),
            _t(language, 'Erro absoluto', 'Absolute error'): _number(results.get('error_val'), language, 6),
            _t(language, 'Passos de tempo (M)', 'Time steps (M)'): results.get('grid_m'),
            _t(language, 'Passos espaciais (N)', 'Space steps (N)'): results.get('grid_n'),
            _t(language, 'Ponto de equilíbrio', 'Break-even point'): _number(results.get('break_even'), language),
            _t(language, 'Perda máxima', 'Max loss'): _number(results.get('max_loss'), language, 4),
        },
        'nested_results': {
            _t(language, 'Gregas (aproximadas)', 'Greeks (approx.)'): {
                'Delta': _number(greeks.get('delta'), language, 4),
                'Gamma': _number(greeks.get('gamma'), language, 4),
                _t(language, 'Theta (diário)', 'Theta (daily)'): _number(greeks.get('theta'), language, 4),
            },
        },
        'interpretation': results.get('interpretation'),
        'charts': _charts({
            _t(language, 'Preço da opção vs. preço do ativo (t=0)', 'Option price vs. underlying (t=0)'): results.get('price_plot'),
            _t(language, 'Solução da equação de difusão (espaço logarítmico)', 'Diffusion equation solution (log space)'): results.get('diffusion_plot'),
        }),
    }


OPTION_TYPE_VALUE_LABELS = {
    'pt': {'option_type': {'call': 'Compra (Call)', 'put': 'Venda (Put)'}},
    'en': {'option_type': {'call': 'Call', 'put': 'Put'}},
}


# --- Strategy screens (computed in the browser) ------------------------------

def build_call_put_payoff_report(parameters, results, language):
    headers = [
        _t(language, 'Preço da Ação no Vencimento', 'Stock Price at Expiration'),
        _t(language, 'Resultado do Titular', "Holder's Payoff"),
        _t(language, 'Resultado do Lançador', "Writer's Payoff"),
    ]
    return {
        'tables': [_money_table(_t(language, 'Payoff por preço', 'Payoff by price'), headers, results.get('rows'), language)],
        'charts': _charts({_t(language, 'Gráfico de Payoff da Opção', 'Option Payoff Diagram'): results.get('chart')}),
    }


def build_asset_put_combination_report(parameters, results, language):
    headers = [
        _t(language, 'Valor do Ativo no Vencimento', 'Asset Value at Expiration'),
        _t(language, 'Valor da Opção de Venda no Vencimento', 'Put Option Value at Expiration'),
        _t(language, 'Combinação', 'Combination'),
    ]
    return {
        'tables': [_money_table(_t(language, 'Valor por preço', 'Value by price'), headers, results.get('rows'), language)],
        'charts': _charts({_t(language, 'Gráfico da Estratégia Protective Put', 'Protective Put Strategy Payoff'): results.get('chart')}),
    }


def build_bull_bear_spread_report(parameters, results, language):
    summary = results.get('summary') or {}
    headers = [
        _t(language, 'Preço da Ação no Vencimento', 'Stock Price at Expiration'),
        _t(language, 'Resultado da Estratégia (L/P)', 'Strategy P/L'),
    ]
    return {
        'results': {
            _t(language, 'Custo de Montagem (Débito)', 'Setup Cost (Debit)'): _money(summary.get('total_debit'), language),
            _t(language, 'Risco Máximo', 'Maximum Risk'): _money(summary.get('max_loss'), language),
            _t(language, 'Retorno Máximo', 'Maximum Return'): _money(summary.get('max_gain'), language),
            _t(language, 'Ponto de Equilíbrio', 'Breakeven Point'): _money(summary.get('breakeven'), language),
            _t(language, 'Retorno Potencial', 'Potential Return'): _percent(summary.get('potential_return'), language),
        },
        'tables': [_money_table(_t(language, 'Resultado por preço', 'Result by price'), headers, results.get('rows'), language)],
        'charts': _charts({_t(language, 'Diagrama de Payoff da Estratégia', 'Strategy Payoff Diagram'): results.get('chart')}),
    }


def build_collar_report(parameters, results, language):
    headers = [
        _t(language, 'Preço da Ação', 'Stock Price'),
        _t(language, 'Resultado da Ação', 'Stock Result'),
        _t(language, 'Resultado da Call Vendida', 'Sold Call Result'),
        _t(language, 'Resultado da Put Comprada', 'Bought Put Result'),
        _t(language, 'Resultado Total', 'Total Result'),
    ]
    return {
        'tables': [_money_table(_t(language, 'Resultado por preço', 'Result by price'), headers, results.get('rows'), language)],
        'charts': _charts({_t(language, 'Gráfico de Payoff da Estratégia Collar', 'Payoff Diagram for Collar Strategy'): results.get('chart')}),
    }


# --- Return & volatility (computed in the browser) ---------------------------

def _return_percent(value, language):
    """A return saved as a fraction (0.05), shown as a percentage (5,00%)."""
    try:
        return _percent(float(value) * 100, language)
    except (TypeError, ValueError):
        return '-'


def build_return_volatility_report(parameters, results, language):
    prices = parameters.get('prices') or []
    discrete = results.get('discrete_returns') or []
    continuous = results.get('continuous_returns') or []
    rows = []
    for index, price in enumerate(prices):
        # The return in row t goes from period t-1 to t; the first period has none.
        has_return = 0 < index <= len(discrete)
        rows.append([
            index + 1,
            _number(price, language),
            _return_percent(discrete[index - 1], language) if has_return else '-',
            _return_percent(continuous[index - 1], language) if has_return and index <= len(continuous) else '-',
        ])
    headers = [
        _t(language, 'Período', 'Period'),
        _t(language, 'Valor do Ativo', 'Asset Value'),
        _t(language, 'Retorno Discreto', 'Discrete Return'),
        _t(language, 'Retorno Contínuo', 'Continuous Return'),
    ]
    return {
        'results': {
            _t(language, 'Número de retornos', 'Number of returns'): len(discrete),
            _t(language, 'Retorno médio discreto (por período)', 'Mean discrete return (per period)'): _return_percent(results.get('mean_discrete'), language),
            _t(language, 'Retorno médio contínuo (por período)', 'Mean continuous return (per period)'): _return_percent(results.get('mean_continuous'), language),
            _t(language, 'Volatilidade discreta (por período)', 'Discrete volatility (per period)'): _return_percent(results.get('volatility_discrete'), language),
            _t(language, 'Volatilidade contínua (por período)', 'Continuous volatility (per period)'): _return_percent(results.get('volatility_continuous'), language),
        },
        'tables': [{
            'title': _t(language, 'Valores e retornos por período', 'Values and returns by period'),
            'headers': headers,
            'rows': rows,
        }],
        'charts': _charts({_t(language, 'Retornos Discretos vs Contínuos', 'Discrete vs Continuous Returns'): results.get('chart')}),
    }


# --- Real options: binomial model (computed in the browser) ------------------

# Above this many steps the lattice table runs for pages (N=50 is 1,326 nodes),
# so the report leaves it out and says so.
BINOMIAL_REPORT_MAX_STEPS = 20


def _lattice_rows(value_tree, option_tree, language):
    """One row per node: step, up moves, project value, option value; highest node first."""
    rows = []
    for step, (values, options) in enumerate(zip(value_tree or [], option_tree or [])):
        for ups in range(len(values) - 1, -1, -1):
            option = options[ups] if ups < len(options) else None
            rows.append([step, ups, _money(values[ups], language), _money(option, language)])
    return rows


def build_binomial_real_option_report(parameters, results, language):
    value_tree = results.get('value_tree') or []
    steps = len(value_tree) - 1
    lattice = {
        'title': _t(language, 'Treliça binomial', 'Binomial lattice'),
        'headers': [
            _t(language, 'Passo (t)', 'Step (t)'),
            _t(language, 'Subidas', 'Up moves'),
            _t(language, 'Valor do Projeto', 'Project Value'),
            _t(language, 'Valor da Opção', 'Option Value'),
        ],
        'rows': [],
    }
    if steps > BINOMIAL_REPORT_MAX_STEPS:
        lattice['note'] = _t(
            language,
            f'A treliça tem {steps} passos e não é impressa no relatório (limite: {BINOMIAL_REPORT_MAX_STEPS} passos). Use Simular Novamente para vê-la na tela.',
            f'The lattice has {steps} steps and is not printed in the report (limit: {BINOMIAL_REPORT_MAX_STEPS} steps). Use Simulate Again to see it on screen.',
        )
    else:
        lattice['rows'] = _lattice_rows(value_tree, results.get('option_tree'), language)

    probability = results.get('probability')
    return {
        'results': {
            _t(language, 'Valor da Opção Real', 'Real Option Value'): _money(results.get('option_value'), language),
            _t(language, 'Fator de Subida (u)', 'Up Factor (u)'): _number(results.get('up_factor'), language, 4),
            _t(language, 'Fator de Descida (d)', 'Down Factor (d)'): _number(results.get('down_factor'), language, 4),
            _t(language, 'Probabilidade Neutra ao Risco (p)', 'Risk-Neutral Probability (p)'): _return_percent(probability, language),
            _t(language, 'Passo de Tempo (Δt, anos)', 'Time Step (Δt, years)'): _number(results.get('dt'), language, 4),
            _t(language, 'VPL Tradicional (sem flexibilidade)', 'Traditional NPV (without flexibility)'): _money(results.get('traditional_npv'), language),
            _t(language, 'VPL Expandido (com valor da opção)', 'Expanded NPV (with option value)'): _money(results.get('expanded_npv'), language),
            _t(language, 'Valor da Flexibilidade', 'Value of Flexibility'): _money(results.get('flexibility_value'), language),
            _t(language, 'Razão Valor da Opção / Custo de Investimento', 'Option Value / Investment Cost Ratio'): _number(results.get('option_ratio'), language, 4),
        },
        'tables': [lattice],
    }


# --- Real options: cash-flow volatility (simulated in the browser) -----------

def _volatility_or_not_available(value, language):
    """Markowitz and VaR divide by the mean NPV; the screen saves None when it is ≤ 0."""
    if value is None:
        return _t(language, 'N/D (VPL médio ≤ 0)', 'N/A (mean NPV ≤ 0)')
    return _return_percent(value, language)


def _cash_flow_volatility_report(parameters, results, language, method_label, extra_results=None):
    cash_flows = parameters.get('cash_flows') or []
    std_devs = parameters.get('std_devs') or []
    rows = [
        [period, _money(cash_flow, language), _money(std_devs[period - 1] if period <= len(std_devs) else None, language)]
        for period, cash_flow in enumerate(cash_flows, start=1)
    ]
    return {
        'results': {
            _t(language, f'Volatilidade estimada ({method_label})', f'Volatility estimate ({method_label})'): _return_percent(results.get('volatility'), language),
            **(extra_results or {}),
            _t(language, 'Média de z', 'Mean of z'): _number(results.get('mean_z'), language, 4),
            _t(language, 'Desvio padrão de z', 'Standard deviation of z'): _number(results.get('std_z'), language, 4),
            _t(language, 'Valor mínimo de z', 'Min value of z'): _number(results.get('min_z'), language, 4),
            _t(language, 'Valor máximo de z', 'Max value of z'): _number(results.get('max_z'), language, 4),
            _t(language, 'VPL médio', 'Average NPV'): _money(results.get('mean_npv'), language),
            _t(language, 'Desvio-padrão do VPL', 'Standard deviation of NPV'): _money(results.get('std_npv'), language),
            _t(language, 'Markowitz: coeficiente de variação do VPL (σ)', 'Markowitz: NPV coefficient of variation (σ)'): _volatility_or_not_available(results.get('markowitz_cv'), language),
            _t(language, 'Abordagem pelo VaR(5%) (σ)', 'VaR(5%) approach (σ)'): _volatility_or_not_available(results.get('var_volatility'), language),
            _t(language, 'Log-retorno do fluxo de caixa (σ)', 'Cash flow log-return (σ)'): _return_percent(results.get('log_cf_volatility'), language),
        },
        'tables': [{
            'title': _t(language, 'Fluxos de caixa esperados', 'Expected cash flows'),
            'headers': [
                _t(language, 'Período', 'Period'),
                _t(language, 'Fluxo de Caixa Esperado', 'Expected Cash Flow'),
                _t(language, 'Desvio Padrão', 'Standard Deviation'),
            ],
            'rows': rows,
        }],
        'charts': _charts({_t(language, 'Histograma de z = ln(V₁/V₀)', 'Histogram of z = ln(V₁/V₀)'): results.get('chart')}),
    }


def build_copeland_antikarov_report(parameters, results, language):
    return _cash_flow_volatility_report(parameters, results, language, 'Copeland & Antikarov', {
        _t(language, 'V₀ (VP dos fluxos esperados)', 'V₀ (PV of the expected cash flows)'): _money(results.get('v0'), language),
    })


def build_herath_park_report(parameters, results, language):
    return _cash_flow_volatility_report(parameters, results, language, 'Herath & Park', {
        _t(language, 'Abordagem de Copeland & Antikarov (σ), para comparação', 'Copeland & Antikarov approach (σ), for comparison'): _return_percent(results.get('ca_volatility'), language),
    })


CASH_FLOW_VOLATILITY_DEFAULTS = {
    'initialInvestment': 500000, 'discountRate': 10, 'numPeriods': 5, 'numSimulations': 1000,
    'uncertaintyPercent': 10, 'seed': '',
    'cash_flows': [125000, 150000, 175000, 200000, 225000],
    'std_devs': [12500, 15000, 17500, 20000, 22500],
}

CASH_FLOW_VOLATILITY_PARAM_LABELS = {
    'pt': {
        'initialInvestment': 'Investimento Inicial (I₀)', 'discountRate': 'Taxa de Desconto (TMA, %)',
        'numPeriods': 'Número de Períodos', 'numSimulations': 'Número de Simulações',
        'uncertaintyPercent': 'Incerteza (Desvio Padrão %)', 'seed': 'Semente',
        'cash_flows': 'Fluxos de Caixa Esperados', 'std_devs': 'Desvios Padrão',
    },
    'en': {
        'initialInvestment': 'Initial Investment (I₀)', 'discountRate': 'Discount Rate (MARR, %)',
        'numPeriods': 'Number of Periods', 'numSimulations': 'Number of Simulations',
        'uncertaintyPercent': 'Uncertainty (Standard Deviation %)', 'seed': 'Seed',
        'cash_flows': 'Expected Cash Flows', 'std_devs': 'Standard Deviations',
    },
}


# --- Stochastic processes (simulated on the server) --------------------------
# The statistics are saved by key (estocasticos/labels.py) and labelled here,
# in the language the report is opened in.

def _stats(stats, language, decimals=4):
    return {stat_label(key, language): _number(value, language, decimals) for key, value in (stats or {}).items()}


def _percent_of(fraction, language):
    try:
        return _percent(float(fraction) * 100, language)
    except (TypeError, ValueError):
        return '-'


def build_markov_chain_report(parameters, results, language):
    states = parameters.get('states') or []
    matrix = parameters.get('transition_matrix') or []
    initial = parameters.get('initial_percentages') or []
    evolution = results.get('evolution') or []
    return {
        'tables': [
            {
                'title': _t(language, 'Matriz de transição (%)', 'Transition matrix (%)'),
                'headers': [_t(language, 'De \\ Para', 'From \\ To'), *states],
                'rows': [[state, *[_percent(value, language) for value in row]] for state, row in zip(states, matrix)],
            },
            {
                'title': _t(language, 'Distribuição inicial', 'Initial distribution'),
                'headers': [_t(language, 'Estado', 'State'), _t(language, 'Probabilidade', 'Probability')],
                'rows': [[state, _percent(value, language)] for state, value in zip(states, initial)],
            },
            {
                'title': _t(language, 'Evolução das probabilidades', 'Evolution of the probabilities'),
                'headers': [_t(language, 'Iteração', 'Iteration'), *states],
                'rows': [[step, *[_percent_of(value, language) for value in vector]] for step, vector in enumerate(evolution)],
            },
        ],
        'charts': _charts({_t(language, 'Evolução das probabilidades dos estados', 'Evolution of state probabilities'): results.get('plot')}),
    }


RANDOM_WALK_DISTRIBUTIONS = {
    'normal': ('Normal N(0, 1)', 'Normal N(0, 1)'),
    'uniform': ('Uniforme U(−1, 1)', 'Uniform U(−1, 1)'),
    'discrete': ('Discreta {−1, 1}', 'Discrete {−1, 1}'),
}


def build_random_walk_report(parameters, results, language):
    statistics = results.get('statistics') or {}
    keys = ('final', 'min', 'max', 'std_theoretical')
    rows = [
        [_t(language, *labels), *[_number(statistics[name].get(key), language, 4) for key in keys]]
        for name, labels in RANDOM_WALK_DISTRIBUTIONS.items() if name in statistics
    ]
    return {
        'tables': [{
            'title': _t(language, 'Resultado por distribuição', 'Result by distribution'),
            'headers': [_t(language, 'Distribuição', 'Distribution'), *[stat_label(key, language) for key in keys]],
            'rows': rows,
        }],
        'charts': _charts({_t(language, 'Random walk com diferentes distribuições', 'Random walk with different distributions'): results.get('plot')}),
    }


def build_random_walk_normal_report(parameters, results, language):
    keys = ('min', 'max', 'mean', 'median', 'variance', 'std')
    rows = [
        [_t(language, f'0% – {item.get("share")}% dos passos', f'0% – {item.get("share")}% of the steps'),
         *[_number((item.get('stats') or {}).get(key), language, 4) for key in keys]]
        for item in results.get('statistics') or []
    ]
    return {
        'tables': [{
            'title': _t(language, 'Estatísticas descritivas das posições', 'Descriptive statistics of the positions'),
            'headers': [_t(language, 'Passos considerados', 'Steps considered'), *[stat_label(key, language) for key in keys]],
            'rows': rows,
        }],
        'charts': _charts({
            _t(language, 'Trajetórias', 'Paths'): results.get('walk_plot'),
            _t(language, 'Distribuição das posições', 'Distribution of the positions'): results.get('histograms_plot'),
        }),
    }


def _diffusion_report(results, language, paths_title, distribution_title):
    return {
        'results': _stats(results.get('statistics'), language),
        'charts': _charts({
            _t(language, *paths_title): results.get('paths_plot'),
            _t(language, *distribution_title): results.get('distribution_plot'),
        }),
    }


def build_abm_report(parameters, results, language):
    return _diffusion_report(results, language, ('Trajetórias simuladas', 'Simulated paths'),
                             ('Distribuição dos valores finais X_T', 'Distribution of the final values X_T'))


def build_gbm_ito_report(parameters, results, language):
    return _diffusion_report(results, language, ('Trajetórias simuladas', 'Simulated paths'),
                             ('Distribuição dos preços finais S_T', 'Distribution of the final prices S_T'))


def build_mean_reversion_report(parameters, results, language):
    return _diffusion_report(results, language, ('Trajetórias simuladas', 'Simulated paths'),
                             ('Distribuição dos valores finais X_T', 'Distribution of the final values X_T'))


def build_gbm_monte_carlo_report(parameters, results, language):
    return {
        'results': _stats(results.get('stats_descriptive'), language),
        'nested_results': {
            _t(language, 'Estatística inferencial (média e IC 95%)', 'Inferential statistics (mean and 95% CI)'):
                _stats(results.get('stats_inferential'), language),
        },
        'charts': _charts({
            _t(language, 'Evolução dos preços', 'Price paths'): results.get('price_plot'),
            _t(language, 'Distribuição dos preços finais', 'Distribution of the final prices'): results.get('distribution_plot'),
            _t(language, 'Convergência da média dos preços finais', 'Convergence of the mean final price'): results.get('convergence_plot'),
        }),
    }


def build_models_comparison_report(parameters, results, language):
    final = results.get('final_values') or {}
    return {
        'results': {
            _t(language, 'Valor final — Random Walk', 'Final value — Random Walk'): _number(final.get('random_walk'), language, 4),
            _t(language, 'Valor final — Movimento Browniano Geométrico', 'Final value — Geometric Brownian Motion'): _number(final.get('gbm'), language, 4),
            _t(language, 'Valor final — Reversão à Média', 'Final value — Mean Reversion'): _number(final.get('mean_reversion'), language, 4),
        },
        'charts': _charts({_t(language, 'Comparação de modelos estocásticos', 'Stochastic models comparison'): results.get('plot_image')}),
    }


SEED_LABELS = {'pt': {'seed': 'Semente'}, 'en': {'seed': 'Seed'}}


def _with_seed(labels):
    return {language: {**names, **SEED_LABELS[language]} for language, names in labels.items()}


DIFFUSION_GRID_LABELS = {
    'pt': {'T': 'Horizonte de tempo (T, anos)', 'dt': 'Passo de tempo (dt)', 'n_simulations': 'Número de simulações'},
    'en': {'T': 'Time horizon (T, years)', 'dt': 'Time step (dt)', 'n_simulations': 'Number of simulations'},
}


def _diffusion_labels(pt, en):
    return _with_seed({'pt': {**pt, **DIFFUSION_GRID_LABELS['pt']}, 'en': {**en, **DIFFUSION_GRID_LABELS['en']}})


# --- Registry ----------------------------------------------------------------

REGISTRY: dict[str, ModelSpec] = {
    FinantialModelsChoices.BLACK_SCHOLES: ModelSpec(
        template='site/financeiros/black-sholes.html',
        build_report=build_black_scholes_report,
        defaults={
            'asset_price': 100.0, 'exercise_price': 100.0, 'time_to_expiration': 30,
            'interest_rate': 5, 'volatility': 20, 'option_type': 'call',
        },
        param_labels=BLACK_SCHOLES_PARAM_LABELS,
        value_labels=OPTION_TYPE_VALUE_LABELS,
    ),
    FinantialModelsChoices.BLACK_SCHOLES_MERTON: ModelSpec(
        template='site/financeiros/black-scholes-merton.html',
        build_report=build_black_scholes_report,
        defaults={
            'asset_price': 100.0, 'exercise_price': 100.0, 'time_to_expiration': 30,
            'interest_rate': 5, 'volatility': 20, 'dividend_yield': 2, 'option_type': 'call',
        },
        param_labels=BLACK_SCHOLES_PARAM_LABELS,
        value_labels=OPTION_TYPE_VALUE_LABELS,
    ),
    FinantialModelsChoices.GENERALIZED_BLACK_SCHOLES_MERTON: ModelSpec(
        template='site/financeiros/generalized-black-scholes-merton.html',
        build_report=build_black_scholes_report,
        defaults={
            'asset_price': 100.0, 'exercise_price': 100.0, 'time_to_expiration': 30,
            'interest_rate': 5, 'volatility': 20, 'cost_of_carry': 5, 'dividend_yield': 0,
            'option_type': 'call',
        },
        param_labels=BLACK_SCHOLES_PARAM_LABELS,
        value_labels=OPTION_TYPE_VALUE_LABELS,
    ),
    FinantialModelsChoices.COX_ROSS: ModelSpec(
        template='site/financeiros/cox-ross-rubinstein.html',
        build_report=build_cox_ross_report,
        defaults={
            'asset_price': 100.0, 'exercise_price': 100.0, 'time_to_expiration': 30,
            'interest_rate': 5, 'volatility': 30, 'option_type': 'call', 'steps': 3,
            'dividend_yield': 0,
        },
        param_labels=BLACK_SCHOLES_PARAM_LABELS,
        value_labels=OPTION_TYPE_VALUE_LABELS,
    ),
    FinantialModelsChoices.MONTE_CARLO_EUROPEAN: ModelSpec(
        template='site/financeiros/options_price_mcs.html',
        build_report=build_monte_carlo_european_report,
        defaults={
            'S0': 100.0, 'K': 100.0, 'T': 1.0, 'r': 5, 'sigma': 20,
            'num_simulacoes': 100000, 'option_type': 'call',
        },
        param_labels=MONTE_CARLO_PARAM_LABELS,
        value_labels=OPTION_TYPE_VALUE_LABELS,
    ),
    FinantialModelsChoices.MONTE_CARLO_AMERICAN: ModelSpec(
        template='site/financeiros/options_price_american_mcs.html',
        build_report=build_monte_carlo_american_report,
        defaults={
            'S0': 100.0, 'K': 100.0, 'T': 1.0, 'r': 5.0, 'sigma': 20.0,
            'num_simulacoes': 10000, 'num_passos': 100, 'option_type': 'put',
        },
        param_labels=MONTE_CARLO_PARAM_LABELS,
        value_labels=OPTION_TYPE_VALUE_LABELS,
    ),
    FinantialModelsChoices.FDM_EUROPEAN: ModelSpec(
        template='site/financeiros/fdm_european.html',
        build_report=build_fdm_european_report,
        defaults={
            'asset_price': 100.0, 'exercise_price': 100.0, 'time_to_expiration': 365,
            'interest_rate': 5, 'volatility': 20, 'option_type': 'call',
        },
        param_labels={
            'pt': {
                'option_type': 'Tipo de Opção', 'asset_price': 'Preço do Ativo (S)',
                'exercise_price': 'Preço de Exercício (K)', 'time_to_expiration': 'Dias até o Vencimento',
                'interest_rate': 'Taxa Livre de Risco (%)', 'volatility': 'Volatilidade (σ, %)',
            },
            'en': {
                'option_type': 'Option Type', 'asset_price': 'Underlying Asset Price (S)',
                'exercise_price': 'Strike Price (K)', 'time_to_expiration': 'Time to Expiration (days)',
                'interest_rate': 'Risk-Free Rate (%)', 'volatility': 'Volatility (σ, %)',
            },
        },
        value_labels=OPTION_TYPE_VALUE_LABELS,
    ),
    FinantialModelsChoices.CALL_PUT_PAYOFF: ModelSpec(
        template='site/financeiros/call_put_options.html',
        build_report=build_call_put_payoff_report,
        defaults={
            'simulationType': 'buy', 'quantity': 100, 'strikePrice': 100,
            'initialValue': 95, 'finalValue': 110, 'divisions': 10,
        },
        param_labels={
            'pt': {
                'simulationType': 'Tipo de Opção', 'quantity': 'Quantidade', 'strikePrice': 'Preço de Exercício',
                'initialValue': 'Preço Mínimo da Ação', 'finalValue': 'Preço Máximo da Ação', 'divisions': 'Passos',
            },
            'en': {
                'simulationType': 'Option Type', 'quantity': 'Quantity', 'strikePrice': 'Strike Price',
                'initialValue': 'Min Stock Price', 'finalValue': 'Max Stock Price', 'divisions': 'Steps',
            },
        },
        # `simulationType` keeps its old values: buy = call, sell = put.
        value_labels={
            'pt': {'simulationType': {'buy': 'Opção de Compra (Call)', 'sell': 'Opção de Venda (Put)'}},
            'en': {'simulationType': {'buy': 'Call Option', 'sell': 'Put Option'}},
        },
    ),
    FinantialModelsChoices.ASSET_PUT_COMBINATION: ModelSpec(
        template='site/financeiros/asset_put_combination.html',
        build_report=build_asset_put_combination_report,
        defaults={
            'quantity': 10, 'strikePriceE': 100, 'initialValue': 100, 'finalValue': 105, 'divisions': 10,
        },
        param_labels={
            'pt': {
                'quantity': 'Quantidade', 'strikePriceE': 'Preço de Exercício', 'initialValue': 'Valor inicial',
                'finalValue': 'Valor final', 'divisions': 'Divisões',
            },
            'en': {
                'quantity': 'Quantity', 'strikePriceE': 'Strike Price', 'initialValue': 'Initial Value',
                'finalValue': 'Final Value', 'divisions': 'Divisions',
            },
        },
    ),
    FinantialModelsChoices.BULL_BEAR_SPREAD: ModelSpec(
        template='site/financeiros/bull_bear_spread.html',
        build_report=build_bull_bear_spread_report,
        defaults={
            'strategyType': 'bullCall', 'strike_long': 30, 'premium_long': 1.1,
            'strike_short': 32, 'premium_short': 0.5, 'quantity': 1000,
            'initialValue': 28, 'finalValue': 34, 'divisions': 10,
        },
        param_labels={
            'pt': {
                'strategyType': 'Tipo de Estratégia', 'strike_long': 'Preço de Exercício (Compra)',
                'premium_long': 'Prêmio (Pago)', 'strike_short': 'Preço de Exercício (Venda)',
                'premium_short': 'Prêmio (Recebido)', 'quantity': 'Quantidade',
                'initialValue': 'Preço Mínimo da Ação', 'finalValue': 'Preço Máximo da Ação', 'divisions': 'Passos',
            },
            'en': {
                'strategyType': 'Strategy Type', 'strike_long': 'Strike Price (Buy)',
                'premium_long': 'Premium (Paid)', 'strike_short': 'Strike Price (Sell)',
                'premium_short': 'Premium (Received)', 'quantity': 'Quantity',
                'initialValue': 'Min Stock Price', 'finalValue': 'Max Stock Price', 'divisions': 'Steps',
            },
        },
        value_labels={
            'pt': {'strategyType': {'bullCall': 'Trava de Alta (c/ Call)', 'bearPut': 'Trava de Baixa (c/ Put)'}},
            'en': {'strategyType': {'bullCall': 'Bull Call Spread', 'bearPut': 'Bear Put Spread'}},
        },
    ),
    FinantialModelsChoices.COLLAR: ModelSpec(
        template='site/financeiros/collar_option.html',
        build_report=build_collar_report,
        defaults={
            'quantity': 100, 'purchasePrice': 50, 'strikePrice': 55,
            'minStockPrice': 40, 'maxStockPrice': 60, 'divisions': 5,
        },
        param_labels={
            'pt': {
                'quantity': 'Quantidade de Ações', 'purchasePrice': 'Preço de Compra da Ação',
                'strikePrice': 'Preço de Exercício (Opções)', 'minStockPrice': 'Preço Mínimo Final da Ação',
                'maxStockPrice': 'Preço Máximo Final da Ação', 'divisions': 'Passos',
            },
            'en': {
                'quantity': 'Quantity', 'purchasePrice': 'Stock Purchase Price',
                'strikePrice': 'Options Strike Price', 'minStockPrice': 'Min Final Stock Price',
                'maxStockPrice': 'Max Final Stock Price', 'divisions': 'Steps',
            },
        },
    ),
    FinantialModelsChoices.RETURN_VOLATILITY: ModelSpec(
        template='site/teoria/volatilidade.html',
        build_report=build_return_volatility_report,
        defaults={'periods': 5, 'prices': [100, 105, 98, 110, 107.5]},
        param_labels={
            'pt': {'periods': 'Número de Períodos', 'prices': 'Valores do Ativo'},
            'en': {'periods': 'Number of Periods', 'prices': 'Asset Values'},
        },
        table_params=('prices',),
    ),
    FinantialModelsChoices.BINOMIAL_REAL_OPTION: ModelSpec(
        template='site/teoria/binomial_model.html',
        build_report=build_binomial_real_option_report,
        defaults={
            'initialValue': 1000000, 'strikePrice': 900000, 'timeToMaturity': 5,
            'riskFreeRate': 5, 'volatility': 20, 'steps': 5,
            'optionType': 'call', 'exerciseStyle': 'european',
        },
        param_labels={
            'pt': {
                'initialValue': 'Valor Inicial do Projeto (V₀)', 'strikePrice': 'Preço de Exercício (Custo do Investimento)',
                'timeToMaturity': 'Tempo até o Vencimento (anos)', 'riskFreeRate': 'Taxa Livre de Risco (%)',
                'volatility': 'Volatilidade Anual (σ, %)', 'steps': 'Número de Passos de Tempo',
                'optionType': 'Tipo de Opção', 'exerciseStyle': 'Estilo de Exercício',
            },
            'en': {
                'initialValue': 'Initial Project Value (V₀)', 'strikePrice': 'Strike Price (Investment Cost)',
                'timeToMaturity': 'Time to Maturity (years)', 'riskFreeRate': 'Risk-Free Rate (%)',
                'volatility': 'Annual Volatility (σ, %)', 'steps': 'Number of Time Steps',
                'optionType': 'Option Type', 'exerciseStyle': 'Exercise Style',
            },
        },
        value_labels={
            'pt': {
                'optionType': {'call': 'Opção de Compra (Opção de Investir)', 'put': 'Opção de Venda (Opção de Abandonar)'},
                'exerciseStyle': {'european': 'Europeia', 'american': 'Americana'},
            },
            'en': {
                'optionType': {'call': 'Call Option (Option to Invest)', 'put': 'Put Option (Option to Abandon)'},
                'exerciseStyle': {'european': 'European', 'american': 'American'},
            },
        },
    ),
    FinantialModelsChoices.COPELAND_ANTIKAROV: ModelSpec(
        template='site/teoria/copeland-antikarov-template.html',
        build_report=build_copeland_antikarov_report,
        defaults=CASH_FLOW_VOLATILITY_DEFAULTS,
        param_labels=CASH_FLOW_VOLATILITY_PARAM_LABELS,
        table_params=('cash_flows', 'std_devs'),
    ),
    FinantialModelsChoices.HERATH_PARK: ModelSpec(
        template='site/teoria/herath_park.html',
        build_report=build_herath_park_report,
        defaults=CASH_FLOW_VOLATILITY_DEFAULTS,
        param_labels=CASH_FLOW_VOLATILITY_PARAM_LABELS,
        table_params=('cash_flows', 'std_devs'),
    ),
    FinantialModelsChoices.MARKOV_CHAIN: ModelSpec(
        template='site/processos-estocasticos/cadeia_markov.html',
        build_report=build_markov_chain_report,
        defaults={
            'num_states': 3, 'states': ['A', 'B', 'C'],
            'transition_matrix': [[70, 20, 10], [10, 80, 10], [20, 30, 50]],
            'initial_percentages': [100, 0, 0], 'iterations': 10,
        },
        param_labels={
            'pt': {'num_states': 'Número de estados', 'iterations': 'Número de iterações', 'states': 'Estados',
                   'transition_matrix': 'Matriz de transição (%)', 'initial_percentages': 'Porcentagens iniciais'},
            'en': {'num_states': 'Number of states', 'iterations': 'Number of iterations', 'states': 'States',
                   'transition_matrix': 'Transition matrix (%)', 'initial_percentages': 'Initial percentages'},
        },
        table_params=('states', 'transition_matrix', 'initial_percentages'),
    ),
    FinantialModelsChoices.RANDOM_WALK: ModelSpec(
        template='site/processos-estocasticos/random_walk.html',
        build_report=build_random_walk_report,
        defaults={'steps': 1000, 'seed': ''},
        param_labels=_with_seed({'pt': {'steps': 'Número de passos'}, 'en': {'steps': 'Number of steps'}}),
    ),
    FinantialModelsChoices.RANDOM_WALK_NORMAL: ModelSpec(
        template='site/processos-estocasticos/random_walk_normal.html',
        build_report=build_random_walk_normal_report,
        defaults={'paths': 5, 'steps': 100, 'seed': ''},
        param_labels=_with_seed({
            'pt': {'paths': 'Número de caminhos', 'steps': 'Número de passos'},
            'en': {'paths': 'Number of paths', 'steps': 'Number of steps'},
        }),
    ),
    FinantialModelsChoices.ARITHMETIC_BROWNIAN_MOTION: ModelSpec(
        template='site/processos-estocasticos/abm.html',
        build_report=build_abm_report,
        defaults={'X0': 100, 'mu': 2.0, 'sigma': 10.0, 'T': 1, 'dt': 0.01, 'n_simulations': 10, 'seed': ''},
        param_labels=_diffusion_labels(
            {'X0': 'Valor inicial (X₀)', 'mu': 'Drift (μ)', 'sigma': 'Volatilidade (σ)'},
            {'X0': 'Initial value (X₀)', 'mu': 'Drift (μ)', 'sigma': 'Volatility (σ)'},
        ),
    ),
    FinantialModelsChoices.GBM_MONTE_CARLO: ModelSpec(
        template='site/processos-estocasticos/monte_carlos.html',
        build_report=build_gbm_monte_carlo_report,
        defaults={'S0': 100, 'mu': 0.15, 'sigma': 0.3, 'time_unit': 'Ano', 'num_periods': 10,
                  'num_simulations': 100, 'seed': ''},
        param_labels=_with_seed({
            'pt': {'S0': 'Preço inicial (S0)', 'mu': 'Retorno anual (μ)', 'sigma': 'Volatilidade anual (σ)',
                   'time_unit': 'Unidade de tempo', 'num_periods': 'Número de períodos', 'num_simulations': 'Número de simulações'},
            'en': {'S0': 'Initial price (S0)', 'mu': 'Annual return (μ)', 'sigma': 'Annual volatility (σ)',
                   'time_unit': 'Time unit', 'num_periods': 'Number of periods', 'num_simulations': 'Number of simulations'},
        }),
        value_labels={
            'pt': {'time_unit': {'Dia': 'Dia', 'Semana': 'Semana', 'Mês': 'Mês', 'Ano': 'Ano'}},
            'en': {'time_unit': {'Dia': 'Day', 'Semana': 'Week', 'Mês': 'Month', 'Ano': 'Year'}},
        },
    ),
    FinantialModelsChoices.GBM_ITO: ModelSpec(
        template='site/processos-estocasticos/mbg_ito.html',
        build_report=build_gbm_ito_report,
        defaults={'S0': 100, 'mu': 0.1, 'sigma': 0.2, 'T': 1, 'dt': 0.01, 'n_simulations': 10, 'seed': ''},
        param_labels=_diffusion_labels(
            {'S0': 'Preço inicial (S₀)', 'mu': 'Taxa de retorno / drift (μ)', 'sigma': 'Volatilidade (σ)'},
            {'S0': 'Initial price (S₀)', 'mu': 'Return rate / drift (μ)', 'sigma': 'Volatility (σ)'},
        ),
    ),
    FinantialModelsChoices.MEAN_REVERSION: ModelSpec(
        template='site/processos-estocasticos/modelo_media.html',
        build_report=build_mean_reversion_report,
        defaults={'S0': 80, 'mu': 100, 'kappa': 1, 'sigma': 5, 'T': 2, 'dt': 0.01, 'n_simulations': 10, 'seed': ''},
        param_labels=_diffusion_labels(
            {'S0': 'Valor inicial (X₀)', 'mu': 'Nível médio (μ)', 'kappa': 'Velocidade de reversão (κ)', 'sigma': 'Volatilidade (σ)'},
            {'S0': 'Initial value (X₀)', 'mu': 'Long-term level (μ)', 'kappa': 'Reversion speed (κ)', 'sigma': 'Volatility (σ)'},
        ),
    ),
    FinantialModelsChoices.MODELS_COMPARISON: ModelSpec(
        template='site/processos-estocasticos/vizualizacao_modelos.html',
        build_report=build_models_comparison_report,
        defaults={'s0': 100, 't': 1, 'dt': 0.01, 'mu_gbm': 0.1, 'sigma_gbm': 0.2,
                  'kappa_mr': 0.5, 'mu_mr': 100, 'sigma_mr': 10, 'seed': ''},
        param_labels=_with_seed({
            'pt': {'s0': 'Valor inicial (S0)', 't': 'Tempo total (T)', 'dt': 'Passo de tempo (dt)',
                   'mu_gbm': 'MBG: taxa de drift (μ)', 'sigma_gbm': 'MBG: volatilidade (σ)',
                   'kappa_mr': 'Reversão: velocidade (κ)', 'mu_mr': 'Reversão: nível de longo prazo (μ)',
                   'sigma_mr': 'Reversão: volatilidade (σ)'},
            'en': {'s0': 'Initial value (S0)', 't': 'Total time (T)', 'dt': 'Time step (dt)',
                   'mu_gbm': 'GBM: drift rate (μ)', 'sigma_gbm': 'GBM: volatility (σ)',
                   'kappa_mr': 'Reversion: speed (κ)', 'mu_mr': 'Reversion: long-term level (μ)',
                   'sigma_mr': 'Reversion: volatility (σ)'},
        }),
    ),
}
