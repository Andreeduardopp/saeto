"""
Single source of truth for every financial model that can be saved.

Each ``model_type`` maps to a ``ModelSpec``, which the save, report, rerun and
list code all read from. To add a model: add the choice, add an entry here and
the coverage test in ``financial_options/tests.py`` passes again.
"""
from dataclasses import dataclass, field
from typing import Callable

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

    def label_parameters(self, parameters, language):
        """Translate parameter names and choice values, in the order of ``param_labels``."""
        names = self.param_labels.get(language) or self.param_labels.get('pt', {})
        values = self.value_labels.get(language) or self.value_labels.get('pt', {})
        ordered_keys = [key for key in names if key in parameters]
        ordered_keys += [key for key in parameters if key not in names]

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
}
