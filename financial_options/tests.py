import json

from django.contrib.auth.models import User
from django.template.loader import get_template
from django.test import TestCase
from django.urls import reverse

from financial_options.models import FinantialModels, FinantialModelsChoices as Choices
from financial_options.report_html import sanitize_report_html
from financial_options.report_registry import REGISTRY

PNG = 'data:image/png;base64,iVBORw0KGgo='

BLACK_SCHOLES_RESULTS = {
    'option_price': '2.4933', 'd1': '0.1283', 'd2': '0.0710', 'n_d1': '55.1', 'n_d2': '52.83',
    'break_even': '102.49', 'max_loss': '2.4933',
    'greeks': {'delta': '0.551', 'gamma': '0.0689', 'theta': '-0.0467', 'vega': '0.1133'},
    'payoff_plot': PNG, 'interpretation': '<p>Interpretação</p>',
}

CASH_FLOW_VOLATILITY_PARAMETERS = {
    'initialInvestment': 500000, 'discountRate': 10, 'numPeriods': 3, 'numSimulations': 1000,
    'uncertaintyPercent': 10, 'seed': 12345,
    'cash_flows': [125000, 150000, 175000], 'std_devs': [12500, 15000, 17500],
}
CASH_FLOW_VOLATILITY_RESULTS = {
    'volatility': 0.0431, 'mean_z': 0.0934, 'std_z': 0.0431, 'min_z': -0.0502, 'max_z': 0.2251,
    'mean_npv': -116100.5, 'std_npv': 20012.3, 'markowitz_cv': None, 'var_5': -149000.1,
    'var_volatility': None, 'log_cf_volatility': 0.1003, 'chart': PNG,
}

DIFFUSION_STATISTICS = {
    'mean': 101.75, 'mean_theoretical': 102.0, 'std': 10.2, 'std_theoretical': 10.0,
    'variance': 104.04, 'variance_theoretical': 100.0, 'min': 75.1, 'max': 130.2, 'p5': 85.0, 'p95': 118.4,
}

# One saved payload per model type, shaped like what each screen sends.
FIXTURES = {
    Choices.BLACK_SCHOLES: (
        {'asset_price': '100', 'exercise_price': '100', 'time_to_expiration': '30',
         'interest_rate': '5', 'volatility': '20', 'option_type': 'call'},
        BLACK_SCHOLES_RESULTS,
    ),
    Choices.BLACK_SCHOLES_MERTON: (
        {'asset_price': '100', 'exercise_price': '100', 'time_to_expiration': '30',
         'interest_rate': '5', 'volatility': '20', 'dividend_yield': '2', 'option_type': 'call'},
        BLACK_SCHOLES_RESULTS,
    ),
    Choices.GENERALIZED_BLACK_SCHOLES_MERTON: (
        {'asset_price': '100', 'exercise_price': '100', 'time_to_expiration': '30', 'interest_rate': '5',
         'volatility': '20', 'cost_of_carry': '5', 'dividend_yield': '0', 'option_type': 'put'},
        BLACK_SCHOLES_RESULTS,
    ),
    Choices.COX_ROSS: (
        {'asset_price': '100', 'exercise_price': '100', 'time_to_expiration': '30', 'interest_rate': '5',
         'volatility': '30', 'dividend_yield': '0', 'steps': '3', 'option_type': 'call'},
        {'option_price': '3.61', 'break_even': '103.61', 'max_loss': '3.61', 'upFactor': '1.0513',
         'downFactor': '0.9512', 'prob': '0.4914', 'dt': '0.0274', 'traditionalNPV': '0.41',
         'expandedNPV': '0.41', 'flexibilityValue': '0', 'optionRatio': '8.8',
         'greeks': {'delta': '0.53', 'gamma': '0.04', 'theta': '-0.05', 'vega': '0.11', 'rho': '0.04'},
         'lattice': '<table><tr><td>100</td></tr></table>', 'interpretation': '<p>CRR</p>'},
    ),
    Choices.MONTE_CARLO_EUROPEAN: (
        {'S0': '100', 'K': '100', 'T': '1', 'r': '5', 'sigma': '20',
         'num_simulacoes': '100000', 'option_type': 'call'},
        {'estimated_price': '10.4506', 'price_plot': PNG, 'distribution_plot': PNG,
         'statistics': {'Mean': '105.1', 'Std': '21.2'}},
    ),
    Choices.MONTE_CARLO_AMERICAN: (
        {'S0': '100', 'K': '100', 'T': '1', 'r': '5', 'sigma': '20',
         'num_simulacoes': '10000', 'num_passos': '100', 'option_type': 'put'},
        {'preco_estimado': '6.0812', 'price_plot': PNG, 'exercise_boundary_plot': PNG, 'convergence_plot': PNG},
    ),
    Choices.FDM_EUROPEAN: (
        {'asset_price': 100, 'exercise_price': 100, 'time_to_expiration': 365,
         'interest_rate': 5, 'volatility': 20, 'option_type': 'call'},
        {'option_price': 10.4497, 'bs_price': 10.4506, 'error_val': 0.000874, 'grid_m': 2651, 'grid_n': 1000,
         'break_even': 110.45, 'max_loss': 10.4497, 'greeks': {'delta': 0.6368, 'gamma': 0.0188, 'theta': -0.0176},
         'price_plot': PNG, 'diffusion_plot': PNG, 'interpretation': '<h4>FDM</h4>'},
    ),
    Choices.CALL_PUT_PAYOFF: (
        {'simulationType': 'buy', 'quantity': 100, 'strikePrice': 100,
         'initialValue': 95, 'finalValue': 110, 'divisions': 5},
        {'rows': [[95, 0, 0], [98.75, 0, 0], [102.5, 250, -250], [106.25, 625, -625], [110, 1000, -1000]],
         'chart': PNG},
    ),
    Choices.ASSET_PUT_COMBINATION: (
        {'quantity': 10, 'strikePriceE': 100, 'initialValue': 90, 'finalValue': 110, 'divisions': 5},
        {'rows': [[90, 10, 1000], [95, 5, 1000], [100, 0, 1000], [105, 0, 1050], [110, 0, 1100]], 'chart': PNG},
    ),
    Choices.BULL_BEAR_SPREAD: (
        {'strategyType': 'bullCall', 'strike_long': 30, 'premium_long': 1.1, 'strike_short': 32,
         'premium_short': 0.5, 'quantity': 1000, 'initialValue': 28, 'finalValue': 34, 'divisions': 5},
        {'summary': {'total_debit': 600, 'max_loss': 600, 'max_gain': 1400, 'breakeven': 30.6,
                     'potential_return': 233.33},
         'rows': [[28, -600], [29.5, -600], [31, 400], [32.5, 1400], [34, 1400]], 'chart': PNG},
    ),
    Choices.COLLAR: (
        {'quantity': 100, 'purchasePrice': 50, 'strikePrice': 55,
         'minStockPrice': 40, 'maxStockPrice': 60, 'divisions': 5},
        {'rows': [[40, -1000, 0, 1500, 500], [45, -500, 0, 1000, 500], [50, 0, 0, 500, 500],
                  [55, 500, 0, 0, 500], [60, 1000, -500, 0, 500]], 'chart': PNG},
    ),
    Choices.RETURN_VOLATILITY: (
        {'periods': 5, 'prices': [100, 105, 98, 110, 107.5]},
        {'discrete_returns': [0.05, -0.0666667, 0.122449, -0.0227273],
         'continuous_returns': [0.0487902, -0.0689929, 0.1155182, -0.0229895],
         'mean_discrete': 0.0207638, 'mean_continuous': 0.0180815,
         'volatility_discrete': 0.0831412, 'volatility_continuous': 0.0810478, 'chart': PNG},
    ),
    Choices.BINOMIAL_REAL_OPTION: (
        {'initialValue': 1000000, 'strikePrice': 900000, 'timeToMaturity': 5, 'riskFreeRate': 5,
         'volatility': 20, 'steps': 2, 'optionType': 'call', 'exerciseStyle': 'european'},
        {'option_value': 338677.52, 'up_factor': 1.371943, 'down_factor': 0.728893, 'probability': 0.628653,
         'dt': 2.5, 'traditional_npv': 100000, 'expanded_npv': 438677.52, 'flexibility_value': 338677.52,
         'option_ratio': 0.376308,
         'value_tree': [[1000000], [728893.41, 1371942.7], [531285.61, 1000000, 1882226.78]],
         'option_tree': [[338677.52], [55478.46, 577695.49], [0, 100000, 982226.78]]},
    ),
    Choices.COPELAND_ANTIKAROV: (
        CASH_FLOW_VOLATILITY_PARAMETERS,
        {**CASH_FLOW_VOLATILITY_RESULTS, 'v0': 645426.21},
    ),
    Choices.HERATH_PARK: (
        CASH_FLOW_VOLATILITY_PARAMETERS,
        {**CASH_FLOW_VOLATILITY_RESULTS, 'volatility': 0.0612, 'std_z': 0.0612, 'ca_volatility': 0.0431},
    ),
    Choices.MARKOV_CHAIN: (
        {'num_states': 2, 'states': ['Sol', 'Chuva'], 'transition_matrix': [[90, 10], [50, 50]],
         'initial_percentages': [100, 0], 'iterations': 2},
        {'evolution': [[1.0, 0.0], [0.9, 0.1], [0.86, 0.14]], 'plot': PNG},
    ),
    Choices.RANDOM_WALK: (
        {'steps': 100, 'seed': 42},
        {'statistics': {
            'normal': {'final': 3.21, 'min': -5.5, 'max': 9.1, 'std_theoretical': 10.0},
            'uniform': {'final': -1.2, 'min': -4.0, 'max': 2.5, 'std_theoretical': 5.7735},
            'discrete': {'final': 4.0, 'min': -6.0, 'max': 8.0, 'std_theoretical': 10.0},
        }, 'plot': PNG},
    ),
    Choices.RANDOM_WALK_NORMAL: (
        {'paths': 5, 'steps': 100, 'seed': 42},
        {'statistics': [
            {'share': share, 'stats': {'min': -3.0, 'max': 4.0, 'mean': 0.25, 'median': 0.2, 'variance': 2.5, 'std': 1.5811}}
            for share in (25, 50, 75, 100)
        ], 'walk_plot': PNG, 'histograms_plot': PNG},
    ),
    Choices.ARITHMETIC_BROWNIAN_MOTION: (
        {'X0': 100, 'mu': 2.0, 'sigma': 10.0, 'T': 1, 'dt': 0.01, 'n_simulations': 10, 'seed': 42},
        {'statistics': DIFFUSION_STATISTICS, 'paths_plot': PNG, 'distribution_plot': PNG},
    ),
    Choices.GBM_MONTE_CARLO: (
        {'S0': 100, 'mu': 0.15, 'sigma': 0.3, 'time_unit': 'Mês', 'num_periods': 10, 'num_simulations': 100, 'seed': 42},
        {'stats_descriptive': {'mean': 113.2, 'std': 30.1, 'min': 50.2, 'max': 210.9, 'expected_return': 13.2},
         'stats_inferential': {'mean': 113.2, 'standard_error': 3.01, 'ci_lower': 107.3, 'ci_upper': 119.1},
         'price_plot': PNG, 'distribution_plot': PNG, 'convergence_plot': PNG},
    ),
    Choices.GBM_ITO: (
        {'S0': 100, 'mu': 0.1, 'sigma': 0.2, 'T': 1, 'dt': 0.01, 'n_simulations': 10, 'seed': 42},
        {'statistics': DIFFUSION_STATISTICS, 'paths_plot': PNG, 'distribution_plot': PNG},
    ),
    Choices.MEAN_REVERSION: (
        {'S0': 80, 'mu': 100, 'kappa': 1, 'sigma': 5, 'T': 2, 'dt': 0.01, 'n_simulations': 10, 'seed': 42},
        {'statistics': DIFFUSION_STATISTICS, 'paths_plot': PNG, 'distribution_plot': PNG},
    ),
    Choices.MODELS_COMPARISON: (
        {'s0': 100, 't': 1, 'dt': 0.01, 'mu_gbm': 0.1, 'sigma_gbm': 0.2, 'kappa_mr': 0.5, 'mu_mr': 100,
         'sigma_mr': 10, 'seed': 42},
        {'final_values': {'random_walk': 93.67, 'gbm': 148.97, 'mean_reversion': 100.18}, 'plot_image': PNG},
    ),
}

# Inputs whose value is one of a fixed set, so the report has to translate the value too.
CHOICE_KEYS = ('option_type', 'simulationType', 'strategyType', 'optionType', 'exerciseStyle', 'time_unit')

# The URL each screen is first opened from (sidebar / overview cards).
SCREEN_URL_NAMES = {
    Choices.BLACK_SCHOLES: 'black_scholes_api',
    Choices.BLACK_SCHOLES_MERTON: 'black_scholes_merton_api',
    Choices.GENERALIZED_BLACK_SCHOLES_MERTON: 'generalized_black_scholes_merton',
    Choices.COX_ROSS: 'cox_ross_rubinstein',
    Choices.MONTE_CARLO_EUROPEAN: 'precificar_opcao',
    Choices.MONTE_CARLO_AMERICAN: 'precificar_opcao_americana',
    Choices.FDM_EUROPEAN: 'european_finite_difference',
    Choices.CALL_PUT_PAYOFF: 'call_put_options',
    Choices.ASSET_PUT_COMBINATION: 'asset_put_combination',
    Choices.BULL_BEAR_SPREAD: 'bull_bear_spread',
    Choices.COLLAR: 'collar_strategy_simulator',
    Choices.RETURN_VOLATILITY: 'volatilidade_template',
    Choices.BINOMIAL_REAL_OPTION: 'binomial_model',
    Choices.COPELAND_ANTIKAROV: 'copeland_antikarov_volatility',
    Choices.HERATH_PARK: 'herath_park_volatility',
    Choices.MARKOV_CHAIN: 'cadeia_markov',
    Choices.RANDOM_WALK: 'random_walk_template',
    Choices.RANDOM_WALK_NORMAL: 'random_walk_normal',
    Choices.ARITHMETIC_BROWNIAN_MOTION: 'abm',
    Choices.GBM_MONTE_CARLO: 'monte_carlos',
    Choices.GBM_ITO: 'mbg_ito',
    Choices.MEAN_REVERSION: 'modelo_reversao_media',
    Choices.MODELS_COMPARISON: 'vizualizacao_modelos',
}


class LoggedInTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ana', password='secret', first_name='Ana', last_name='Silva')
        self.client.force_login(self.user)

    def set_language(self, language):
        session = self.client.session
        session['language'] = language
        session.save()

    def create_simulation(self, model_type):
        parameters, results = FIXTURES[model_type]
        return FinantialModels.objects.create(
            usuario=self.user, model_type=model_type, parameters=parameters, results=results, report='online',
        )


class RegistryCoverageTests(TestCase):
    def test_every_model_type_has_a_registry_entry(self):
        missing = [choice for choice in Choices.values if choice not in REGISTRY]
        self.assertEqual(missing, [], 'Add these model types to financial_options/report_registry.py')

    def test_every_registry_entry_has_a_fixture_and_an_existing_template(self):
        for model_type, spec in REGISTRY.items():
            with self.subTest(model_type=model_type):
                self.assertIn(model_type, FIXTURES)
                get_template(spec.template)

    def test_every_parameter_is_labelled_in_both_languages(self):
        for model_type, spec in REGISTRY.items():
            parameters, _ = FIXTURES[model_type]
            for language in ('pt', 'en'):
                with self.subTest(model_type=model_type, language=language):
                    labelled = spec.label_parameters(parameters, language)
                    unlabelled = [key for key in parameters if key in labelled]
                    self.assertEqual(unlabelled, [], 'Add these keys to param_labels')

    def test_every_choice_value_is_labelled_in_both_languages(self):
        for model_type, spec in REGISTRY.items():
            parameters, _ = FIXTURES[model_type]
            for language in ('pt', 'en'):
                for key, value in parameters.items():
                    if key not in CHOICE_KEYS:
                        continue
                    with self.subTest(model_type=model_type, language=language, key=key):
                        labels = spec.value_labels.get(language, {}).get(key, {})
                        self.assertIn(value, labels, 'Add this value to value_labels')


class SaveFinancialModelTests(LoggedInTestCase):
    def post(self, payload):
        body = payload if isinstance(payload, str) else json.dumps(payload)
        return self.client.post(reverse('save_financial_model'), body, content_type='application/json')

    def test_anonymous_request_is_redirected_to_login(self):
        self.client.logout()
        response = self.post({'model_type': 'BLACK_SCHOLES', 'parameters': {'a': 1}, 'results': {'b': 2}})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/admin/login/'))
        self.assertFalse(FinantialModels.objects.exists())

    def test_missing_fields_return_400(self):
        response = self.post({'model_type': 'BLACK_SCHOLES', 'parameters': {'a': 1}})
        self.assertEqual(response.status_code, 400)

    def test_invalid_json_returns_400(self):
        response = self.post('{not json')
        self.assertEqual(response.status_code, 400)

    def test_unknown_model_type_is_rejected(self):
        response = self.post({'model_type': 'NOT_A_MODEL', 'parameters': {'a': 1}, 'results': {'b': 2}})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(FinantialModels.objects.exists())

    def test_every_registry_type_is_saved_with_online_report(self):
        for model_type in REGISTRY:
            with self.subTest(model_type=model_type):
                parameters, results = FIXTURES[model_type]
                response = self.post({'model_type': model_type, 'parameters': parameters, 'results': results})
                self.assertEqual(response.status_code, 200)
                saved = FinantialModels.objects.get(id=response.json()['id'])
                self.assertEqual(saved.report.name, 'online')
                self.assertEqual(saved.parameters, parameters)
                self.assertEqual(saved.results, results)

    def test_limit_is_40_models_per_user(self):
        for _ in range(40):
            self.create_simulation(Choices.COLLAR)
        parameters, results = FIXTURES[Choices.COLLAR]
        response = self.post({'model_type': Choices.COLLAR, 'parameters': parameters, 'results': results})
        self.assertEqual(response.status_code, 400)
        self.assertIn('40', response.json()['error'])
        self.assertEqual(FinantialModels.objects.filter(usuario=self.user).count(), 40)


class ReportViewTests(LoggedInTestCase):
    def test_report_renders_for_every_registry_type_in_both_languages(self):
        for model_type in REGISTRY:
            simulation = self.create_simulation(model_type)
            for language, title in (('pt', 'Relatório - '), ('en', 'Report - ')):
                with self.subTest(model_type=model_type, language=language):
                    self.set_language(language)
                    response = self.client.get(reverse('view_report', args=[simulation.id]))
                    self.assertEqual(response.status_code, 200)
                    self.assertTemplateUsed(response, 'site/financeiros/report/report_template.html')
                    self.assertContains(response, f'<h1>{title}{simulation.get_model_type_display()}</h1>', html=True)

    def test_cox_ross_report_shows_the_down_factor(self):
        simulation = self.create_simulation(Choices.COX_ROSS)
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.context['results']['Fator de baixa (d)'], '0.9512')

        self.set_language('en')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.context['results']['Down factor (d)'], '0.9512')

    def test_older_reports_are_translated(self):
        """The six screens that predate the registry label their results too."""
        expected = {
            Choices.BLACK_SCHOLES: ('Valor da Opção', 'Option Value'),
            Choices.BLACK_SCHOLES_MERTON: ('Perda Máxima', 'Maximum Loss'),
            Choices.GENERALIZED_BLACK_SCHOLES_MERTON: ('Ponto de Equilíbrio', 'Break-Even Point'),
            Choices.COX_ROSS: ('VPL expandido (com valor da opção)', 'Expanded NPV (with option value)'),
            Choices.MONTE_CARLO_EUROPEAN: ('Preço Estimado da Opção', 'Estimated Option Price'),
            Choices.MONTE_CARLO_AMERICAN: ('Preço Estimado da Opção', 'Estimated Option Price'),
        }
        for model_type, (pt_label, en_label) in expected.items():
            simulation = self.create_simulation(model_type)
            for language, label in (('pt', pt_label), ('en', en_label)):
                with self.subTest(model_type=model_type, language=language):
                    self.set_language(language)
                    response = self.client.get(reverse('view_report', args=[simulation.id]))
                    self.assertIn(label, response.context['results'])

    def test_cox_ross_probability_survives_a_missing_value(self):
        simulation = self.create_simulation(Choices.COX_ROSS)
        simulation.results = {**simulation.results, 'prob': ''}
        simulation.save()
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.context['results']['Probabilidade neutra ao risco (%)'], '-')

    def test_saved_html_is_sanitized_before_it_is_rendered(self):
        simulation = self.create_simulation(Choices.COX_ROSS)
        simulation.results = {
            **simulation.results,
            'interpretation': '<p onclick="steal()">Delta<script>alert(1)</script></p>',
            'lattice': '<table><tr><td class="bg-success">100</td></tr></table><img src=x onerror=alert(1)>',
        }
        simulation.save()
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        content = response.content.decode()
        self.assertIn('<p>Delta</p>', content)
        self.assertIn('<td class="bg-success">100</td>', content)
        self.assertNotIn('steal()', content)  # the page's own print button keeps its onclick
        self.assertNotIn('alert(1)', content)
        self.assertNotIn('onerror', content)

    def test_strategy_report_formats_table_and_translates_labels(self):
        simulation = self.create_simulation(Choices.BULL_BEAR_SPREAD)

        self.set_language('pt')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.context['parameters']['Tipo de Estratégia'], 'Trava de Alta (c/ Call)')
        self.assertEqual(response.context['results']['Retorno Potencial'], '233,33%')
        table = response.context['tables'][0]
        self.assertEqual(table['headers'][1], 'Resultado da Estratégia (L/P)')
        self.assertEqual(table['rows'][0], ['R$ 28,00', '-R$ 600,00'])
        self.assertContains(response, 'class="data-table"')

        self.set_language('en')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.context['parameters']['Strategy Type'], 'Bull Call Spread')
        self.assertEqual(response.context['tables'][0]['rows'][3], ['R$ 32.50', 'R$ 1,400.00'])

    def test_parameters_follow_the_label_order(self):
        simulation = self.create_simulation(Choices.FDM_EUROPEAN)
        simulation.parameters = dict(reversed(list(simulation.parameters.items())))
        simulation.save()
        self.set_language('en')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(list(response.context['parameters'])[:2], ['Option Type', 'Underlying Asset Price (S)'])

    def test_unknown_model_type_returns_404(self):
        simulation = self.create_simulation(Choices.BLACK_SCHOLES)
        FinantialModels.objects.filter(id=simulation.id).update(model_type='LEGACY')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.status_code, 404)

    def test_other_users_report_is_not_found(self):
        simulation = self.create_simulation(Choices.BLACK_SCHOLES)
        self.client.force_login(User.objects.create_user('bia', password='secret'))
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.status_code, 404)


class ReturnVolatilityTests(LoggedInTestCase):
    def test_report_shows_the_prices_in_the_table_not_in_the_parameters(self):
        simulation = self.create_simulation(Choices.RETURN_VOLATILITY)

        self.set_language('pt')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.context['parameters'], {'Número de Períodos': 5})
        self.assertEqual(response.context['results']['Volatilidade discreta (por período)'], '8,31%')
        self.assertEqual(response.context['results']['Volatilidade contínua (por período)'], '8,10%')
        rows = response.context['tables'][0]['rows']
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0], [1, '100,00', '-', '-'])
        self.assertEqual(rows[2], [3, '98,00', '-6,67%', '-6,90%'])

        self.set_language('en')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.context['parameters'], {'Number of Periods': 5})
        self.assertEqual(response.context['results']['Mean discrete return (per period)'], '2.08%')
        self.assertEqual(response.context['tables'][0]['rows'][4], [5, '107.50', '-2.27%', '-2.30%'])

    def test_rerun_fills_the_table_with_the_saved_prices(self):
        simulation = self.create_simulation(Choices.RETURN_VOLATILITY)
        simulation.parameters = {'periods': 3, 'prices': [10, 12.5, 11]}
        simulation.save()
        response = self.client.get(reverse('rerun_simulation', args=[simulation.id]))
        self.assertContains(
            response,
            '<script id="volatilityInitialData" type="application/json">{"periods": 3, "prices": [10, 12.5, 11]}</script>',
        )

    def test_screen_validates_periods_and_prices(self):
        for language, messages in (
            ('pt', ('entre ${MIN_PERIODS} e ${MAX_PERIODS}', 'maiores que zero')),
            ('en', ('between ${MIN_PERIODS} and ${MAX_PERIODS}', 'greater than zero')),
        ):
            with self.subTest(language=language):
                self.set_language(language)
                response = self.client.get(reverse('volatilidade_template'))
                for message in messages:
                    self.assertContains(response, message)
                # A top-level `let` breaks the second time the screen is injected (plan §2.6).
                self.assertNotContains(response, 'let returnsChart;')


class BinomialRealOptionTests(LoggedInTestCase):
    def test_report_formats_results_and_lists_the_lattice_nodes(self):
        simulation = self.create_simulation(Choices.BINOMIAL_REAL_OPTION)

        self.set_language('pt')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        parameters = response.context['parameters']
        self.assertEqual(parameters['Tipo de Opção'], 'Opção de Compra (Opção de Investir)')
        self.assertEqual(parameters['Estilo de Exercício'], 'Europeia')
        results = response.context['results']
        self.assertEqual(results['Valor da Opção Real'], 'R$ 338.677,52')
        self.assertEqual(results['Probabilidade Neutra ao Risco (p)'], '62,87%')
        self.assertEqual(results['Fator de Subida (u)'], '1,3719')
        table = response.context['tables'][0]
        self.assertEqual(table['headers'][2], 'Valor do Projeto')
        # One row per node (1 + 2 + 3), highest node of each step first.
        self.assertEqual(len(table['rows']), 6)
        self.assertEqual(table['rows'][0], [0, 0, 'R$ 1.000.000,00', 'R$ 338.677,52'])
        self.assertEqual(table['rows'][3], [2, 2, 'R$ 1.882.226,78', 'R$ 982.226,78'])
        self.assertEqual(table['rows'][5], [2, 0, 'R$ 531.285,61', 'R$ 0,00'])

        self.set_language('en')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.context['parameters']['Exercise Style'], 'European')
        self.assertEqual(response.context['results']['Expanded NPV (with option value)'], 'R$ 438,677.52')
        self.assertEqual(response.context['tables'][0]['rows'][1], [1, 1, 'R$ 1,371,942.70', 'R$ 577,695.49'])

    def test_report_leaves_out_a_lattice_too_long_to_print(self):
        simulation = self.create_simulation(Choices.BINOMIAL_REAL_OPTION)
        tree = [[100.0] * (step + 1) for step in range(22)]
        simulation.results = {**simulation.results, 'value_tree': tree, 'option_tree': tree}
        simulation.save()
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        table = response.context['tables'][0]
        self.assertEqual(table['rows'], [])
        self.assertIn('21 passos', table['note'])
        self.assertContains(response, 'class="table-note"')
        self.assertNotContains(response, 'class="data-table"')

    def test_rerun_selects_the_saved_choices(self):
        simulation = self.create_simulation(Choices.BINOMIAL_REAL_OPTION)
        simulation.parameters = {**simulation.parameters, 'optionType': 'put', 'exerciseStyle': 'american'}
        simulation.save()
        response = self.client.get(reverse('rerun_simulation', args=[simulation.id]))
        self.assertContains(response, '<option value="put" selected>')
        self.assertContains(response, '<option value="american" selected>')
        self.assertContains(response, 'id="steps" class="form-control" min="1" max="50" step="1" value="2"')

    def test_screen_rejects_a_probability_outside_0_1(self):
        for language, message in (('pt', 'fora do intervalo de 0 a 1'), ('en', 'outside 0 to 1')):
            with self.subTest(language=language):
                self.set_language(language)
                response = self.client.get(reverse('binomial_model'))
                self.assertContains(response, message)
                self.assertContains(response, 'if (!(p > 0 && p < 1)) return null;')
                self.assertNotContains(response, 'onclick="calculateOptions()"')


class CashFlowVolatilityTests(LoggedInTestCase):
    def test_report_shows_the_cash_flows_in_the_table_and_marks_a_negative_npv(self):
        simulation = self.create_simulation(Choices.COPELAND_ANTIKAROV)

        self.set_language('pt')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        parameters = response.context['parameters']
        self.assertNotIn('Fluxos de Caixa Esperados', parameters)
        self.assertEqual(parameters['Semente'], 12345)
        results = response.context['results']
        self.assertEqual(results['Volatilidade estimada (Copeland & Antikarov)'], '4,31%')
        self.assertEqual(results['V₀ (VP dos fluxos esperados)'], 'R$ 645.426,21')
        self.assertEqual(results['Markowitz: coeficiente de variação do VPL (σ)'], 'N/D (VPL médio ≤ 0)')
        self.assertEqual(response.context['tables'][0]['rows'][1], [2, 'R$ 150.000,00', 'R$ 15.000,00'])

        self.set_language('en')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.context['parameters']['Seed'], 12345)
        self.assertEqual(response.context['results']['VaR(5%) approach (σ)'], 'N/A (mean NPV ≤ 0)')

    def test_herath_park_report_compares_with_copeland_antikarov(self):
        simulation = self.create_simulation(Choices.HERATH_PARK)
        simulation.results = {**simulation.results, 'mean_npv': 100000, 'markowitz_cv': 0.2001}
        simulation.save()
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        results = response.context['results']
        self.assertEqual(results['Volatilidade estimada (Herath & Park)'], '6,12%')
        self.assertEqual(results['Abordagem de Copeland & Antikarov (σ), para comparação'], '4,31%')
        self.assertEqual(results['Markowitz: coeficiente de variação do VPL (σ)'], '20,01%')

    def test_rerun_fills_the_seed_and_the_cash_flow_table(self):
        simulation = self.create_simulation(Choices.HERATH_PARK)
        response = self.client.get(reverse('rerun_simulation', args=[simulation.id]))
        self.assertContains(response, 'id="seed" class="form-control" min="0" max="4294967295" step="1" value="12345"')
        self.assertContains(response, '"cash_flows": [125000, 150000, 175000], "std_devs": [12500, 15000, 17500]')
        self.assertContains(response, "modelType: 'HERATH_PARK'")

    def test_screens_draw_from_the_seeded_generator(self):
        for url_name in ('copeland_antikarov_volatility', 'herath_park_volatility'):
            for language, message in (('pt', 'Deixe vazio para sorteios novos'), ('en', 'Leave empty for new random draws')):
                with self.subTest(url_name=url_name, language=language):
                    self.set_language(language)
                    response = self.client.get(reverse(url_name))
                    self.assertContains(response, message)
                    self.assertContains(response, 'saetoRandom(p.seed)')
                    self.assertNotContains(response, 'Math.random')
                    self.assertNotContains(response, 'onclick=')


class RerunViewTests(LoggedInTestCase):
    def test_stochastic_reruns_keep_the_translated_statistic_labels(self):
        model_types = (
            Choices.RANDOM_WALK, Choices.RANDOM_WALK_NORMAL,
            Choices.ARITHMETIC_BROWNIAN_MOTION, Choices.GBM_ITO,
            Choices.MEAN_REVERSION, Choices.GBM_MONTE_CARLO,
        )
        for model_type in model_types:
            simulation = self.create_simulation(model_type)
            for language, expected in (('pt', 'Desvio padrão'), ('en', 'Standard deviation')):
                with self.subTest(model_type=model_type, language=language):
                    self.set_language(language)
                    initial = self.client.get(reverse(SCREEN_URL_NAMES[model_type]))
                    rerun = self.client.get(reverse('rerun_simulation', args=[simulation.id]))
                    self.assertEqual(rerun.context['stat_labels'], initial.context['stat_labels'])
                    self.assertEqual(rerun.context['stat_labels']['std'], expected)
                    if model_type in (Choices.RANDOM_WALK, Choices.RANDOM_WALK_NORMAL):
                        self.assertContains(rerun, expected)
                    else:
                        self.assertContains(rerun, f'"std": {json.dumps(expected)}')
                    self.assertNotContains(rerun, '<th></th>')

    def test_rerun_renders_the_registry_template_for_every_type(self):
        for model_type, spec in REGISTRY.items():
            with self.subTest(model_type=model_type):
                simulation = self.create_simulation(model_type)
                response = self.client.get(reverse('rerun_simulation', args=[simulation.id]))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, spec.template)
                self.assertEqual(response.context['initial_data'], {**spec.defaults, **simulation.parameters})

    def test_old_save_is_filled_in_with_defaults(self):
        simulation = self.create_simulation(Choices.BULL_BEAR_SPREAD)
        simulation.parameters = {'strategyType': 'bearPut', 'strike_long': 40}
        simulation.save()
        response = self.client.get(reverse('rerun_simulation', args=[simulation.id]))
        self.assertEqual(response.context['initial_data']['strike_long'], 40)
        self.assertEqual(response.context['initial_data']['quantity'], 1000)
        self.assertContains(response, 'id="bearPutSpread" value="bearPut" checked')

    def test_unknown_model_type_redirects_to_the_list(self):
        simulation = self.create_simulation(Choices.BLACK_SCHOLES)
        FinantialModels.objects.filter(id=simulation.id).update(model_type='LEGACY')
        response = self.client.get(reverse('rerun_simulation', args=[simulation.id]))
        self.assertRedirects(response, reverse('simulation_list'), fetch_redirect_response=False)


class ScreenFirstLoadTests(LoggedInTestCase):
    def test_every_screen_opens_with_the_registry_defaults(self):
        self.assertEqual(set(SCREEN_URL_NAMES), set(REGISTRY))
        for model_type, url_name in SCREEN_URL_NAMES.items():
            with self.subTest(model_type=model_type):
                spec = REGISTRY[model_type]
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, spec.template)
                self.assertEqual(response.context['initial_data'], spec.defaults)

    def test_every_screen_saves_through_the_shared_helper(self):
        for model_type, url_name in SCREEN_URL_NAMES.items():
            with self.subTest(model_type=model_type):
                response = self.client.get(reverse(url_name))
                self.assertContains(response, 'name="csrfmiddlewaretoken"')
                # Screens that calculate on the server save through saetoServerScreen, which calls saetoSaveProject.
                content = response.content.decode()
                self.assertTrue('saetoSaveProject({' in content or 'saetoServerScreen;' in content)
                self.assertContains(response, f"modelType: '{model_type}'")
                self.assertContains(response, reverse('save_financial_model'))
                # The helper owns the request; no screen builds its own save fetch any more.
                self.assertNotContains(response, 'X-CSRFToken')


class SanitizeReportHtmlTests(TestCase):
    def test_keeps_the_tags_the_saved_fragments_use(self):
        html = ('<h4>Título</h4><p>Delta de <strong>0.55</strong></p>'
                '<ul><li>item</li></ul><div class="alert alert-success">ok</div>'
                '<table><tbody><tr><td colspan="3" class="bg-success">100</td></tr></tbody></table><hr><br>')
        self.assertEqual(sanitize_report_html(html), html)

    def test_drops_scripts_handlers_and_links(self):
        self.assertEqual(sanitize_report_html('<script>alert(1)</script>'), '')
        self.assertEqual(sanitize_report_html('<p onclick="x()" style="color:red">hi</p>'), '<p>hi</p>')
        self.assertEqual(sanitize_report_html('<a href="javascript:x()">link</a>'), 'link')
        self.assertEqual(sanitize_report_html('<img src=x onerror=alert(1)>'), '')
        self.assertEqual(sanitize_report_html('<svg><script>alert(1)</script></svg>rest'), 'rest')
        self.assertEqual(sanitize_report_html('<td class="a&quot;b">x</td>'), '<td>x</td>')

    def test_escapes_text_and_closes_open_tags(self):
        self.assertEqual(sanitize_report_html('a < b & c'), 'a &lt; b &amp; c')
        self.assertEqual(sanitize_report_html('<div><p>text'), '<div><p>text</p></div>')
        self.assertEqual(sanitize_report_html('</p>text'), 'text')
        self.assertEqual(sanitize_report_html(None), '')


class ScreenValidationTests(LoggedInTestCase):
    def test_call_put_screen_asks_for_an_option_type(self):
        for language, label in (('pt', 'Opção de Compra (Call)'), ('en', 'Call Option')):
            with self.subTest(language=language):
                self.set_language(language)
                response = self.client.get(reverse('call_put_options'))
                self.assertContains(response, label)

    def test_every_strategy_screen_limits_the_steps_to_5_50(self):
        """A bigger range makes a report table that runs for pages (open item 2)."""
        url_names = ['call_put_options', 'asset_put_combination', 'bull_bear_spread', 'collar_strategy_simulator']
        for url_name in url_names:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertContains(response, 'divisions < 5 || divisions > 50')


class SimulationListTests(LoggedInTestCase):
    def test_every_registry_type_gets_report_and_rerun_buttons(self):
        for model_type in REGISTRY:
            self.create_simulation(model_type)
        response = self.client.get(reverse('simulation_list') + '?page=1')
        content = response.content.decode()
        page_size = len(response.context['page_obj'])
        self.assertEqual(content.count('rerun-btn'), page_size)
        self.assertEqual(content.count('View Report') + content.count('Ver Relatório'), page_size)
