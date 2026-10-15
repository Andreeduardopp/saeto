import json
import math
import statistics
import uuid
from unittest import mock

from django.contrib.auth.models import User
from django.template.loader import get_template
from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from financial_options.models import FinantialModels, FinantialModelsChoices as Choices
from financial_options.report_html import sanitize_report_html
from estocasticos.labels import STAT_LABELS
from financial_options.report_registry import (
    MONTE_CARLO_AMERICAN_LIMITS, MONTE_CARLO_EUROPEAN_LIMITS, REGISTRY,
)

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

    def test_custom_name_is_trimmed_and_shown_in_the_report(self):
        parameters, results = FIXTURES[Choices.MARKOV_CHAIN]
        name = 'Exemplo de Markov <script>alert(1)</script>'
        response = self.post({'name': f'  {name}  ', 'model_type': Choices.MARKOV_CHAIN,
                              'parameters': parameters, 'results': results})
        self.assertEqual(response.status_code, 200)
        saved = FinantialModels.objects.get(id=response.json()['id'])
        self.assertEqual(saved.name, name)
        self.assertEqual(response.json()['name'], name)
        for language, label in (('pt', 'Projeto:'), ('en', 'Project:')):
            self.set_language(language)
            report = self.client.get(reverse('view_report', args=[saved.id]))
            self.assertContains(report, label)
            self.assertContains(report, 'Exemplo de Markov &lt;script&gt;alert(1)&lt;/script&gt;')
            self.assertNotContains(report, '<script>alert(1)</script>')

    def test_omitted_or_blank_names_keep_the_automatic_name(self):
        parameters, results = FIXTURES[Choices.MARKOV_CHAIN]
        for extra in ({}, {'name': ''}, {'name': '   '}):
            response = self.post({'model_type': Choices.MARKOV_CHAIN, 'parameters': parameters,
                                  'results': results, **extra})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['name'].startswith('Markov Chain - '))

    def test_name_validation(self):
        parameters, results = FIXTURES[Choices.MARKOV_CHAIN]
        for language, error in (('pt', 'O nome do projeto'), ('en', 'Project name')):
            self.set_language(language)
            for name in (None, 123, [], {}, 'x' * 256):
                with self.subTest(language=language, name=name):
                    response = self.post({'name': name, 'model_type': Choices.MARKOV_CHAIN,
                                          'parameters': parameters, 'results': results})
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(error, response.json()['error'])
        self.assertFalse(FinantialModels.objects.exists())
        response = self.post({'name': 'x' * 255, 'model_type': Choices.MARKOV_CHAIN,
                              'parameters': parameters, 'results': results})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], 'x' * 255)

    def test_non_object_json_returns_400(self):
        for payload in ('[]', 'null', '123'):
            self.assertEqual(self.post(payload).status_code, 400)

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


class ProjectNamingTests(LoggedInTestCase):
    def rename(self, simulation, name):
        return self.client.post(reverse('update_simulation_name'),
                                {'id': str(simulation.id), 'name': name}, content_type='application/json')

    def test_every_model_can_be_named_renamed_and_reopened_in_both_languages(self):
        for model_type in REGISTRY:
            with self.subTest(model_type=model_type):
                parameters, results = FIXTURES[model_type]
                original_name = f'Exemplo — {model_type}'
                response = self.client.post(reverse('save_financial_model'), {
                    'model_type': model_type, 'name': original_name,
                    'parameters': parameters, 'results': results,
                }, content_type='application/json')
                self.assertEqual(response.status_code, 200)
                simulation = FinantialModels.objects.get(id=response.json()['id'])
                self.assertEqual(simulation.name, original_name)

                for language in ('pt', 'en'):
                    self.set_language(language)
                    new_name = f'Cenário revisto {language} — {model_type} <teste> & "2026"'
                    response = self.rename(simulation, f'  {new_name}  ')
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()['name'], new_name)
                    simulation.refresh_from_db()
                    self.assertEqual(simulation.name, new_name)
                    self.assertEqual(simulation.parameters, parameters)
                    self.assertEqual(simulation.results, results)
                    # This is the newest save, so it is on the first history page.
                    history = self.client.get(reverse('simulation_list'))
                    self.assertContains(history, escape(new_name))
                    report = self.client.get(reverse('view_report', args=[simulation.id]))
                    self.assertEqual(report.context['project_name'], new_name)
                    self.assertContains(report, escape(new_name))
                    rerun = self.client.get(reverse('rerun_simulation', args=[simulation.id]))
                    self.assertEqual(rerun.context['initial_data'], {**REGISTRY[model_type].defaults, **parameters})

    def test_rename_rejects_invalid_names_without_changing_the_project(self):
        simulation = self.create_simulation(Choices.BLACK_SCHOLES)
        original_name = simulation.name
        for name in ('', '  ', 'x' * 256, None, 12, [], {}):
            with self.subTest(name=name):
                response = self.rename(simulation, name)
                self.assertEqual(response.status_code, 400)
                simulation.refresh_from_db()
                self.assertEqual(simulation.name, original_name)
        self.assertEqual(self.rename(simulation, 'x' * 255).status_code, 200)
        simulation.refresh_from_db()
        self.assertEqual(simulation.name, 'x' * 255)

    def test_literal_financial_model_name_is_preserved_on_save_and_rename(self):
        parameters, results = FIXTURES[Choices.BLACK_SCHOLES]
        response = self.client.post(reverse('save_financial_model'), {
            'model_type': Choices.BLACK_SCHOLES, 'name': 'Financial Model',
            'parameters': parameters, 'results': results,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        simulation = FinantialModels.objects.get(id=response.json()['id'])
        self.assertEqual(simulation.name, 'Financial Model')
        self.assertEqual(self.rename(simulation, 'Outro nome').status_code, 200)
        self.assertEqual(self.rename(simulation, 'Financial Model').status_code, 200)
        simulation.refresh_from_db()
        self.assertEqual(simulation.name, 'Financial Model')

    def test_rename_handles_invalid_json_and_missing_or_unknown_ids(self):
        simulation = self.create_simulation(Choices.BLACK_SCHOLES)
        for body in ('{', '[]', 'null', '123'):
            response = self.client.post(reverse('update_simulation_name'), body, content_type='application/json')
            self.assertEqual(response.status_code, 400)
        for invalid_id, status in ((None, 400), ('bad-id', 400), (str(uuid.uuid4()), 404)):
            response = self.client.post(reverse('update_simulation_name'),
                                        {'id': invalid_id, 'name': 'Novo'}, content_type='application/json')
            self.assertEqual(response.status_code, status)
        other = User.objects.create_user('bia', password='secret')
        self.client.force_login(other)
        self.assertEqual(self.rename(simulation, 'Alheio').status_code, 404)
        self.client.logout()
        self.assertEqual(self.rename(simulation, 'Anônimo').status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('update_simulation_name')).status_code, 405)

    def test_existing_projects_can_be_renamed_at_the_40_project_limit(self):
        for _ in range(40):
            simulation = self.create_simulation(Choices.BLACK_SCHOLES)
        self.assertEqual(self.rename(simulation, 'Revisado no limite').status_code, 200)
        simulation.refresh_from_db()
        self.assertEqual(simulation.name, 'Revisado no limite')
        self.assertEqual(FinantialModels.objects.count(), 40)


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


def _sample_std(values):
    # A series too short to be accepted still needs a payload to post.
    return statistics.stdev(values) if len(values) > 1 else 0.0


# The nine prices of the handbook example, also used by tests/js/ for the screen.
HANDBOOK_PRICES = [26.27103, 26.17373, 26.48509, 26.37806, 26.00832,
                   26.25157, 26.41698, 27.14673, 26.57266]


def return_volatility_payload(prices, name='', periods_per_year=None, frequency=None):
    """A save payload shaped like the screen's, for any series of prices.

    ``periods_per_year`` adds the optional annualization the screen only sends when
    the run was annualized (plan §6).
    """
    discrete = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]
    continuous = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
    mean_continuous = statistics.fmean(continuous)
    volatility_continuous = _sample_std(continuous)
    parameters = {'periods': len(prices), 'prices': prices}
    results = {
        'discrete_returns': discrete,
        'continuous_returns': continuous,
        'mean_discrete': statistics.fmean(discrete),
        'mean_continuous': mean_continuous,
        'volatility_discrete': _sample_std(discrete),
        'volatility_continuous': volatility_continuous,
        'chart': PNG,
    }
    if periods_per_year is not None:
        parameters['frequency'] = 'daily' if frequency is None else frequency
        parameters['periodsPerYear'] = periods_per_year
        results['annual_rate_equivalent'] = math.exp(periods_per_year * mean_continuous) - 1
        results['annual_volatility_continuous'] = math.sqrt(periods_per_year) * volatility_continuous
    return {
        'name': name,
        'model_type': Choices.RETURN_VOLATILITY,
        'parameters': parameters,
        'results': results,
    }


class ReturnVolatilityTests(LoggedInTestCase):
    def test_report_shows_the_prices_in_the_table_not_in_the_parameters(self):
        simulation = self.create_simulation(Choices.RETURN_VOLATILITY)

        self.set_language('pt')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.context['parameters'], {'Número de preços (N)': 5})
        results = response.context['results']
        self.assertEqual(results['Número de preços (N)'], 5)
        self.assertEqual(results['Número de retornos (n = N − 1)'], 4)
        self.assertEqual(results['Divisor do desvio-padrão amostral (n − 1 = N − 2)'], 3)
        self.assertEqual(results['Volatilidade discreta (por período)'], '8,3141%')
        self.assertEqual(results['Volatilidade contínua (por período)'], '8,1048%')
        table = response.context['tables'][0]
        self.assertEqual(table['headers'][:2], ['Período (t)', 'Preço do ativo S(t)'])
        self.assertEqual(len(table['rows']), 5)
        # Four percentage decimals, and a price with the digits it was given.
        self.assertEqual(table['rows'][0], [1, '100', '-', '-'])
        self.assertEqual(table['rows'][2], [3, '98', '-6,6667%', '-6,8993%'])
        self.assertIn('não tem retorno', table['note'])

        self.set_language('en')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.context['parameters'], {'Number of prices (N)': 5})
        self.assertEqual(response.context['results']['Mean discrete return (per period)'], '2.0764%')
        self.assertEqual(response.context['tables'][0]['headers'][1], 'Asset price S(t)')
        self.assertEqual(response.context['tables'][0]['rows'][4], [5, '107.5', '-2.2727%', '-2.2990%'])

    def test_report_keeps_the_precision_of_the_prices_and_four_decimals_of_the_returns(self):
        """The nine prices of the handbook, as the screen and the copy show them."""
        simulation = self.create_simulation(Choices.RETURN_VOLATILITY)
        payload = return_volatility_payload(HANDBOOK_PRICES)
        simulation.parameters = payload['parameters']
        simulation.results = payload['results']
        simulation.save()

        self.set_language('pt')
        results = self.client.get(reverse('view_report', args=[simulation.id])).context['results']
        self.assertEqual(results['Número de preços (N)'], 9)
        self.assertEqual(results['Número de retornos (n = N − 1)'], 8)
        # Nine prices give eight returns, and the sample divisor is 7.
        self.assertEqual(results['Divisor do desvio-padrão amostral (n − 1 = N − 2)'], 7)
        self.assertEqual(results['Retorno médio contínuo (por período)'], '0,1427%')
        self.assertEqual(results['Volatilidade contínua (por período)'], '1,5485%')
        rows = self.client.get(reverse('view_report', args=[simulation.id])).context['tables'][0]['rows']
        # Five decimals of the price survive the report; only the separator changes.
        self.assertEqual(rows[0], [1, '26,27103', '-', '-'])
        self.assertEqual(rows[1][1], '26,17373')
        self.assertEqual(rows[1][3], '-0,3711%')

        self.set_language('en')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.context['results']['Continuous volatility (per period)'], '1.5485%')
        self.assertEqual(response.context['tables'][0]['rows'][0][1], '26.27103')

    def test_the_four_decimals_belong_to_this_screen_only(self):
        """Other models keep the precision of their own screens (plan §5)."""
        simulation = self.create_simulation(Choices.COPELAND_ANTIKAROV)
        self.set_language('pt')
        results = self.client.get(reverse('view_report', args=[simulation.id])).context['results']
        volatility = [value for key, value in results.items() if 'Volatilidade' in key]
        self.assertTrue(volatility)
        for value in volatility:
            self.assertRegex(value, r'^-?\d+,\d{2}%$')

    def test_rerun_fills_the_table_with_the_saved_prices(self):
        simulation = self.create_simulation(Choices.RETURN_VOLATILITY)
        simulation.parameters = {'periods': 3, 'prices': [10, 12.5, 11]}
        simulation.save()
        response = self.client.get(reverse('rerun_simulation', args=[simulation.id]))
        self.assertContains(
            response,
            '<script id="volatilityInitialData" type="application/json">{"periods": 3, "prices": [10, 12.5, 11]}</script>',
        )

    def test_rerun_keeps_the_example_reachable_and_offers_the_saved_data_back(self):
        simulation = self.create_simulation(Choices.RETURN_VOLATILITY)
        simulation.parameters = {'periods': 3, 'prices': [10, 12.5, 11]}
        simulation.save()
        response = self.client.get(reverse('rerun_simulation', args=[simulation.id]))
        # The example of the screen stays available next to the saved series.
        self.assertContains(
            response,
            '<script id="volatilityExampleData" type="application/json">'
            '{"periods": 5, "prices": [100, 105, 98, 110, 107.5]}</script>',
        )
        self.assertContains(response, 'id="restoreButton"')
        # A first load has no saved data to restore, so it does not offer it.
        self.assertNotContains(self.client.get(reverse('volatilidade_template')), 'id="restoreButton"')

    def test_screen_accepts_from_3_to_1000_prices(self):
        response = self.client.get(reverse('volatilidade_template'))
        self.assertContains(response, 'min="3"')
        self.assertContains(response, 'max="1000"')
        limits = response.context['limits']
        self.assertEqual(limits, {'min_prices': 3, 'max_prices': 1000,
                                  'min_periods_per_year': 1, 'max_periods_per_year': 100000})

    def test_screen_names_the_count_and_the_price_column(self):
        for language, labels in (
            ('pt', ('Número de preços (N)', 'Preço do ativo S(t)')),
            ('en', ('Number of prices (N)', 'Asset price S(t)')),
        ):
            with self.subTest(language=language):
                self.set_language(language)
                response = self.client.get(reverse('volatilidade_template'))
                for label in labels:
                    self.assertContains(response, label)

    def test_screen_explains_n_the_returns_and_the_sample_divisor(self):
        for language, texts in (
            ('pt', ('Como estes números são obtidos',
                    'n = N − 1',
                    'n − 1 = N − 2',
                    'R(t) = [S(t) − S(t−1)] / S(t−1)',
                    'r(t) = ln[S(t) / S(t−1)]',
                    'quatro casas decimais percentuais',
                    'na unidade dos períodos informados')),
            ('en', ('How these numbers are obtained',
                    'n = N − 1',
                    'n − 1 = N − 2',
                    'R(t) = [S(t) − S(t−1)] / S(t−1)',
                    'four percentage decimals',
                    'in the unit of the periods entered')),
        ):
            with self.subTest(language=language):
                self.set_language(language)
                response = self.client.get(reverse('volatilidade_template'))
                for text in texts:
                    self.assertContains(response, escape(text))
                # The divisor of this series is written next to the summary, and the
                # derivation stays one expansion away from the main action.
                self.assertContains(response, 'id="statsNote"')
                self.assertContains(response, 'id="statsDetails"')

    def annualized_simulation(self, periods_per_year=252, frequency='daily'):
        """The nine prices of the handbook, saved with an annualization."""
        simulation = self.create_simulation(Choices.RETURN_VOLATILITY)
        payload = return_volatility_payload(HANDBOOK_PRICES, periods_per_year=periods_per_year,
                                            frequency=frequency)
        simulation.parameters = payload['parameters']
        simulation.results = payload['results']
        simulation.save()
        return simulation

    def test_report_of_an_annualized_run_shows_m_the_rate_and_the_formulas(self):
        """The 43,28% and 24,58% of the report, with four decimals (plan §6)."""
        simulation = self.annualized_simulation()

        self.set_language('pt')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        parameters = response.context['parameters']
        self.assertEqual(parameters['Número de preços (N)'], 9)
        self.assertEqual(parameters['Frequência dos preços'], 'Diária')
        self.assertEqual(parameters['Períodos por ano (m)'], 252)
        results = response.context['results']
        self.assertEqual(results['Períodos por ano (m)'], 252)
        self.assertEqual(results['Taxa anual equivalente (do retorno logarítmico médio)'], '43,2764%')
        self.assertEqual(results['Volatilidade anual (contínua)'], '24,5816%')
        # The per-period results stay, unchanged, next to the annual ones.
        self.assertEqual(results['Volatilidade contínua (por período)'], '1,5485%')
        self.assertEqual(results['Retorno médio contínuo (por período)'], '0,1427%')
        # The annualization prints before the prices table, next to the numbers.
        annual_table, prices_table = response.context['tables']
        self.assertEqual(annual_table['title'], 'Anualização')
        self.assertEqual(len(prices_table['rows']), 9)
        for text in ('exp(m × média dos log-retornos) − 1',
                     '√m × desvio-padrão amostral dos log-retornos',
                     'm = 252 períodos por ano',
                     'não é o retorno acumulado da janela',
                     'raiz do tempo pressupõe',
                     'não uma previsão'):
            self.assertIn(text, annual_table['note'])
        self.assertNotIn('rows', annual_table)

        self.set_language('en')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.context['parameters']['Price frequency'], 'Daily')
        self.assertEqual(response.context['parameters']['Periods per year (m)'], 252)
        self.assertEqual(
            response.context['results']['Equivalent annual rate (from the mean log return)'],
            '43.2764%')
        self.assertEqual(response.context['results']['Annual volatility (continuous)'], '24.5816%')
        self.assertEqual(response.context['tables'][0]['title'], 'Annualization')
        self.assertIn('not the accumulated return of the window',
                      response.context['tables'][0]['note'])

    def test_a_monthly_annualization_keeps_its_own_m_and_label(self):
        simulation = self.annualized_simulation(periods_per_year=12, frequency='monthly')
        self.set_language('pt')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.context['parameters']['Frequência dos preços'], 'Mensal')
        self.assertEqual(response.context['results']['Períodos por ano (m)'], 12)
        self.assertEqual(response.context['results']['Volatilidade anual (contínua)'], '5,3641%')
        self.assertIn('m = 12 períodos por ano', response.context['tables'][0]['note'])

    def test_an_annual_frequency_leaves_m_1_and_matches_the_per_period_values(self):
        simulation = self.annualized_simulation(periods_per_year=1, frequency='annual')
        self.set_language('pt')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.context['parameters']['Frequência dos preços'], 'Anual')
        self.assertEqual(response.context['results']['Períodos por ano (m)'], 1)
        # m = 1 leaves the annual block equal to the per-period one (√1 = 1).
        self.assertEqual(response.context['results']['Volatilidade anual (contínua)'],
                          response.context['results']['Volatilidade contínua (por período)'])

    def test_a_project_saved_without_annualization_is_not_reported_as_annualized(self):
        """A project saved before the option existed re-runs and reports as it was."""
        simulation = self.create_simulation(Choices.RETURN_VOLATILITY)
        self.set_language('pt')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(response.context['parameters'], {'Número de preços (N)': 5})
        for key in response.context['results']:
            self.assertNotIn('anual', key.lower())
        # Only the prices table: no annualization block was added.
        self.assertEqual(len(response.context['tables']), 1)

        rerun = self.client.get(reverse('rerun_simulation', args=[simulation.id]))
        # The data block of the screen carries no m, so the option opens switched off.
        self.assertNotContains(rerun, '"periodsPerYear":')
        self.assertContains(rerun, 'id="annualizeToggle"')

    def test_rerun_opens_the_project_with_the_annualization_it_was_saved_with(self):
        simulation = self.annualized_simulation(periods_per_year=1, frequency='annual')
        response = self.client.get(reverse('rerun_simulation', args=[simulation.id]))
        initial = response.context['initial_data']
        self.assertEqual(initial['periodsPerYear'], 1)
        self.assertEqual(initial['frequency'], 'annual')
        self.assertEqual(initial['prices'], HANDBOOK_PRICES)
        # The screen reads them from this block to open the option already on.
        self.assertContains(response, '"periodsPerYear": 1')

    def test_screen_offers_the_optional_annualization_with_its_formulas(self):
        for language, texts in (
            ('pt', ('2. Configuração', 'Anualizar os resultados (opcional)',
                    'Frequência dos preços', 'Períodos por ano (m)',
                    'Diária (252 períodos por ano)',
                    'Mensal (12 períodos por ano)', 'Anual (1 período por ano)',
                    'convenções usuais, não a contagem de preços',
                    'Resultados anuais',
                    'Taxa anual equivalente a partir do retorno logarítmico médio',
                    'Volatilidade anual (contínua)',
                    'exp(m × μ) − 1', '√m × σ',
                    'não a contagem de preços da amostra',
                    'não é o retorno acumulado da janela',
                    'não uma previsão garantida')),
            ('en', ('2. Settings', 'Annualize the results (optional)',
                    'Price frequency', 'Periods per year (m)',
                    'Daily (252 periods per year)',
                    'Monthly (12 periods per year)', 'Annual (1 period per year)',
                    'usual conventions, not a count of the prices',
                    'Annual results',
                    'Equivalent annual rate from the mean log return',
                    'Annual volatility (continuous)',
                    'exp(m × μ) − 1', '√m × σ',
                    'not the count of prices in the sample',
                    'not the accumulated return of the window',
                    'not a guaranteed forecast')),
        ):
            with self.subTest(language=language):
                self.set_language(language)
                response = self.client.get(reverse('volatilidade_template'))
                for text in texts:
                    self.assertContains(response, escape(text))
                for element in ('id="annualizeToggle"', 'id="annualFrequency"',
                                'id="periodsPerYear"', 'id="annualBlock"', 'id="annualPending"'):
                    self.assertContains(response, element)
                # The range of m comes from the registry, like the range of N.
                self.assertContains(response, 'max="100000"')
                # The results section moved down: Data, Settings, Results.
                self.assertContains(response, '3. Result')

    def test_screen_imports_a_file_and_says_how_it_must_be_organised(self):
        for language, texts in (
            ('pt', ('Importar um arquivo com os preços', 'Como o arquivo deve estar organizado',
                    'Um preço por linha', 'sem separador de milhar',
                    'baixar o modelo CSV', 'Coluna de preços')),
            ('en', ('Import a file with the prices', 'How the file must be organised',
                    'One price per row', 'no thousands separator',
                    'download the CSV model', 'Price column')),
        ):
            with self.subTest(language=language):
                self.set_language(language)
                response = self.client.get(reverse('volatilidade_template'))
                for text in texts:
                    self.assertContains(response, escape(text))
                self.assertContains(response, 'id="priceFileInput"')
                self.assertContains(response, 'accept=".csv,.txt,.xlsx')
                # The Excel reader is fetched only when a spreadsheet is opened, and
                # the browser checks the file it gets against this hash.
                self.assertContains(response, 'cdn.sheetjs.com')
                self.assertContains(response, 'sha384-')
                # The example moved out of the action row but stays one click away.
                self.assertNotContains(response, 'id="exampleButton"')
                self.assertContains(response, 'id="exampleLink"')

    def test_screen_validates_the_count_and_the_prices(self):
        for language, messages in (
            ('pt', ('entre ${MIN_PRICES} e ${MAX_PRICES}', 'maior que zero',
                    'número inteiro', 'Dados alterados. Recalcule para atualizar.')),
            ('en', ('between ${MIN_PRICES} and ${MAX_PRICES}', 'greater than zero',
                    'whole number', 'Data changed. Recalculate to update.')),
        ):
            with self.subTest(language=language):
                self.set_language(language)
                response = self.client.get(reverse('volatilidade_template'))
                for message in messages:
                    self.assertContains(response, message)
                # A top-level `let` breaks the second time the screen is injected (plan §2.6).
                self.assertNotContains(response, 'let returnsChart;')


class ReturnVolatilitySaveTests(LoggedInTestCase):
    """The size rule of the screen, checked again when the series is saved."""

    def post(self, payload):
        return self.client.post(reverse('save_financial_model'), json.dumps(payload),
                                content_type='application/json')

    def series(self, count):
        return [100 + (index % 7) for index in range(count)]

    def test_a_year_of_prices_is_saved_and_reported(self):
        response = self.post(return_volatility_payload(self.series(249), name='WEGE3'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        simulation = FinantialModels.objects.get(name='WEGE3')
        self.assertEqual(len(simulation.parameters['prices']), 249)
        self.assertEqual(len(simulation.results['discrete_returns']), 248)
        report = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(report.context['results']['Número de retornos (n = N − 1)'], 248)

    def test_the_limits_of_the_screen_are_the_limits_of_the_save(self):
        for count in (3, 300, 1000):
            with self.subTest(count=count):
                response = self.post(return_volatility_payload(self.series(count), name=f'ok-{count}'))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()['success'])
        for count in (2, 1001):
            with self.subTest(count=count):
                response = self.post(return_volatility_payload(self.series(count), name=f'no-{count}'))
                self.assertEqual(response.status_code, 400)
                self.assertIn('de 3 a 1000 preços', response.json()['error'])
        self.assertEqual(FinantialModels.objects.count(), 3)

    def test_a_price_that_is_not_a_positive_number_names_its_row(self):
        for price in (0, -5, 'abc', None, True):
            with self.subTest(price=price):
                payload = return_volatility_payload(self.series(5))
                payload['parameters']['prices'][2] = price
                response = self.post(payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn('linha 3', response.json()['error'])
        self.assertFalse(FinantialModels.objects.exists())

    def test_results_that_do_not_match_the_series_are_refused(self):
        payload = return_volatility_payload(self.series(5))
        payload['results']['continuous_returns'] = payload['results']['continuous_returns'][:2]
        response = self.post(payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn('4 retornos para 5 preços', response.json()['error'])

        payload = return_volatility_payload(self.series(5))
        payload['parameters']['periods'] = 9
        response = self.post(payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn('não corresponde', response.json()['error'])

        # A value that is not a number is said to be that, not counted as a mismatch.
        payload = return_volatility_payload(self.series(5))
        payload['parameters']['periods'] = '5'
        response = self.post(payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn('deve ser um número', response.json()['error'])
        self.assertNotIn('não corresponde', response.json()['error'])

        payload = return_volatility_payload(self.series(5))
        payload['results']['volatility_continuous'] = None
        response = self.post(payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn('números finitos', response.json()['error'])
        self.assertFalse(FinantialModels.objects.exists())

    def test_a_non_finite_number_is_refused(self):
        payload = return_volatility_payload(self.series(5))
        payload['results']['mean_continuous'] = float('inf')
        response = self.client.post(reverse('save_financial_model'), json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(FinantialModels.objects.exists())

    def test_an_annualized_run_is_saved_with_m_and_its_annual_results(self):
        response = self.post(return_volatility_payload(HANDBOOK_PRICES, name='WEGE3 anual',
                                                       periods_per_year=252))
        self.assertEqual(response.status_code, 200)
        simulation = FinantialModels.objects.get(name='WEGE3 anual')
        self.assertEqual(simulation.parameters['periodsPerYear'], 252)
        self.assertEqual(simulation.parameters['frequency'], 'daily')
        # Saved unrounded; the report is what rounds it to four decimals.
        self.assertAlmostEqual(simulation.results['annual_rate_equivalent'], 0.4327644793, places=10)
        report = self.client.get(reverse('view_report', args=[simulation.id]))
        self.assertEqual(report.context['results']['Volatilidade anual (contínua)'], '24,5816%')

    def test_m_must_be_a_whole_number_inside_its_range(self):
        for periods in (0, -252, 2.5, '252', True, 100001):
            with self.subTest(periods=periods):
                payload = return_volatility_payload(self.series(5), periods_per_year=252)
                payload['parameters']['periodsPerYear'] = periods
                response = self.post(payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn('número inteiro de 1 a 100000', response.json()['error'])
        # A flat series, so even the largest m stays inside the representable range:
        # an annualization that overflows arrives with a non-finite number instead.
        for periods in (1, 12, 52, 252, 100000):
            with self.subTest(periods=periods):
                payload = return_volatility_payload([100] * 5, name=f'm-{periods}',
                                                    periods_per_year=periods)
                self.assertEqual(self.post(payload).status_code, 200)
        self.assertEqual(FinantialModels.objects.count(), 5)

    def test_an_annualization_without_its_numbers_or_with_a_strange_frequency_is_refused(self):
        # Annual results with no m: a rate nobody could check.
        payload = return_volatility_payload(self.series(5), periods_per_year=252)
        del payload['parameters']['periodsPerYear']
        response = self.post(payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn('precisa dos períodos por ano (m)', response.json()['error'])

        for value in (None, float('inf'), 'x'):
            with self.subTest(value=value):
                payload = return_volatility_payload(self.series(5), periods_per_year=252)
                payload['results']['annual_volatility_continuous'] = value
                response = self.post(payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn('devem ser números finitos', response.json()['error'])

        payload = return_volatility_payload(self.series(5), periods_per_year=252)
        del payload['results']['annual_rate_equivalent']
        self.assertEqual(self.post(payload).status_code, 400)

        for frequency in ('hourly', 'weekly', 'custom', '', [], 7):
            with self.subTest(frequency=frequency):
                payload = return_volatility_payload(self.series(5), periods_per_year=252,
                                                    frequency=frequency)
                response = self.post(payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn('frequência dos preços não é uma das opções',
                              response.json()['error'])
        self.assertFalse(FinantialModels.objects.exists())

    def test_a_run_that_was_not_annualized_is_saved_as_it_is(self):
        payload = return_volatility_payload(self.series(5), name='por período')
        self.assertEqual(self.post(payload).status_code, 200)
        simulation = FinantialModels.objects.get(name='por período')
        self.assertNotIn('periodsPerYear', simulation.parameters)
        self.assertNotIn('annual_rate_equivalent', simulation.results)

    def test_the_message_follows_the_language_of_the_session(self):
        self.set_language('en')
        response = self.post(return_volatility_payload(self.series(2)))
        self.assertIn('from 3 to 1000 prices', response.json()['error'])

        payload = return_volatility_payload(self.series(5), periods_per_year=0)
        response = self.post(payload)
        self.assertIn('whole number from 1 to 100000', response.json()['error'])

    def test_models_without_a_payload_rule_are_untouched(self):
        response = self.post({'name': 'bs', 'model_type': Choices.BLACK_SCHOLES,
                              'parameters': {'a': 1}, 'results': {'b': 2}})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])


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


class MonteCarloScreenTests(LoggedInTestCase):
    """The two Monte Carlo screens: one source for the HTML, the limit and the message."""

    EUROPEAN = {'S0': '100', 'K': '100', 'T': '1', 'r': '5', 'sigma': '20',
                'num_simulacoes': '1000', 'option_type': 'call'}
    AMERICAN = {'S0': '100', 'K': '100', 'T': '1', 'r': '5', 'sigma': '20',
                'num_simulacoes': '1000', 'num_passos': '10', 'option_type': 'put'}

    def post(self, url_name, data, **overrides):
        return self.client.post(reverse(url_name), {**data, **overrides})

    def test_each_screen_publishes_the_limits_the_server_enforces(self):
        screens = [
            ('precificar_opcao', MONTE_CARLO_EUROPEAN_LIMITS),
            ('precificar_opcao_americana', MONTE_CARLO_AMERICAN_LIMITS),
        ]
        for url_name, limits in screens:
            with self.subTest(url_name=url_name):
                content = self.client.get(reverse(url_name)).content.decode()
                self.assertIn('min="%s"' % limits['min_simulations'], content)
                self.assertIn('max="%s"' % limits['max_simulations'], content)
                self.assertIn('min="%s"' % limits['min_volatility'], content)
                self.assertIn('max="%s"' % limits['max_volatility'], content)
                if 'max_steps' in limits:
                    self.assertIn('max="%s"' % limits['max_steps'], content)

    def test_the_american_screen_names_its_own_ceiling_not_a_tenfold_one(self):
        """The HTML offered 100,000 while the server accepted 10,000 (plan section 10, U6)."""
        content = self.client.get(reverse('precificar_opcao_americana')).content.decode()
        self.assertIn('max="10000"', content)
        self.assertNotIn('max="100000"', content)
        self.assertIn('10.000', content)
        self.assertNotIn('100.000', content)

        inside = self.post('precificar_opcao_americana', self.AMERICAN, num_simulacoes='10000')
        self.assertEqual(inside.status_code, 200)
        outside = self.post('precificar_opcao_americana', self.AMERICAN, num_simulacoes='10001')
        self.assertEqual(outside.status_code, 400)
        message = outside.json()['errors']['num_simulacoes']
        self.assertIn('10.000', message)
        self.assertNotIn('100.000', message)

    def test_the_european_screen_keeps_its_million_simulations(self):
        self.assertEqual(self.post('precificar_opcao', self.EUROPEAN).status_code, 200)
        refused = self.post('precificar_opcao', self.EUROPEAN, num_simulacoes='1000001')
        self.assertEqual(refused.status_code, 400)
        self.assertIn('1.000.000', refused.json()['errors']['num_simulacoes'])

    def test_both_screens_answer_in_the_language_of_the_session(self):
        cases = [
            ('precificar_opcao', self.EUROPEAN, {'num_simulacoes': '5'}, 'num_simulacoes',
             'Número de Simulações deve estar entre 1.000 e 1.000.000.',
             'Number of Simulations must be between 1,000 and 1,000,000.'),
            ('precificar_opcao_americana', self.AMERICAN, {'num_passos': '5'}, 'num_passos',
             'Número de Passos no Tempo deve estar entre 10 e 1.000.',
             'Number of Time Steps must be between 10 and 1,000.'),
            ('precificar_opcao_americana', self.AMERICAN, {'S0': '0'}, 'S0',
             'Preço Atual do Ativo (S0) deve ser maior que 0.',
             'Initial Asset Price (S0) must be greater than 0.'),
            ('precificar_opcao', self.EUROPEAN, {'option_type': 'straddle'}, 'option_type',
             'Tipo de Opção: opção inválida.', 'Option Type: invalid option.'),
        ]
        for url_name, data, overrides, field, pt, en in cases:
            for language, expected in (('pt', pt), ('en', en)):
                with self.subTest(url_name=url_name, overrides=overrides, language=language):
                    self.set_language(language)
                    response = self.post(url_name, data, **overrides)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json()['errors'][field], expected)

    def test_every_field_that_is_wrong_is_named_at_once(self):
        response = self.post('precificar_opcao_americana', self.AMERICAN,
                             S0='abc', K='-1', num_simulacoes='10.5', num_passos='0')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(sorted(response.json()['errors']), ['K', 'S0', 'num_passos', 'num_simulacoes'])

    def test_an_empty_or_missing_field_is_a_message_not_a_server_error(self):
        for overrides in ({'T': ''}, {'sigma': '   '}, {'r': 'abc'}):
            with self.subTest(overrides=overrides):
                response = self.post('precificar_opcao', self.EUROPEAN, **overrides)
                self.assertEqual(response.status_code, 400)
        payload = {key: value for key, value in self.EUROPEAN.items() if key != 'K'}
        response = self.client.post(reverse('precificar_opcao'), payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn('K', response.json()['errors'])

    def test_the_results_come_back_as_numbers_and_statistics_by_key(self):
        """The screen formats them in the session language; the saved run keeps the number."""
        data = self.post('precificar_opcao', self.EUROPEAN).json()
        self.assertIsInstance(data['preco_estimado'], float)
        for table in ('stats_descriptive', 'stats_inferential'):
            self.assertTrue(data[table])
            for key, value in data[table].items():
                self.assertIn(key, STAT_LABELS, 'Label %s in estocasticos/labels.py' % key)
                self.assertIsInstance(value, float)
        american = self.post('precificar_opcao_americana', self.AMERICAN).json()
        self.assertIsInstance(american['preco_estimado'], float)

    def test_a_saved_run_is_reported_in_the_language_it_is_opened_in(self):
        simulation = FinantialModels.objects.create(
            usuario=self.user, model_type=Choices.MONTE_CARLO_EUROPEAN, report='online',
            parameters=FIXTURES[Choices.MONTE_CARLO_EUROPEAN][0],
            results={'estimated_price': 10.450583572, 'price_plot': PNG, 'distribution_plot': PNG,
                     'statistics': {'mean': 105.1234567, 'std': 21.2}},
        )
        expected = {
            'pt': ('Preço Estimado da Opção', '10,4506', 'Média', '105,1235'),
            'en': ('Estimated Option Price', '10.4506', 'Mean', '105.1235'),
        }
        for language, (price_label, price, label, stat) in expected.items():
            with self.subTest(language=language):
                self.set_language(language)
                response = self.client.get(reverse('view_report', args=[simulation.id]))
                self.assertEqual(response.context['results'][price_label], price)
                table = list(response.context['nested_results'].values())[0]
                self.assertEqual(table[label], stat)

    def test_a_run_saved_before_the_keys_keeps_the_labels_it_was_saved_with(self):
        simulation = self.create_simulation(Choices.MONTE_CARLO_EUROPEAN)
        self.set_language('en')
        response = self.client.get(reverse('view_report', args=[simulation.id]))
        table = list(response.context['nested_results'].values())[0]
        self.assertEqual(table, {'Mean': '105.1', 'Std': '21.2'})

    def test_a_failed_simulation_says_so_without_leaking_its_cause(self):
        with mock.patch('financial_options.api.views.option_price_use_case',
                        side_effect=RuntimeError('matrix is singular at row 7')):
            with self.assertLogs('financial_options.api.views', level='ERROR'):
                self.set_language('pt')
                response = self.post('precificar_opcao', self.EUROPEAN)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()['error'], 'Ocorreu um erro inesperado durante a simulação.')
        self.assertNotIn('singular', response.json()['error'])

    def test_neither_screen_opens_a_browser_dialog_for_an_error(self):
        """A modal dialog blocks the screen and cannot be read in the session language."""
        for url_name in ('precificar_opcao', 'precificar_opcao_americana'):
            with self.subTest(url_name=url_name):
                content = self.client.get(reverse(url_name)).content.decode()
                self.assertNotIn('alert(', content)
                self.assertIn('role="alert"', content)
