import numpy as np
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from estocasticos.use_cases.abm_use_case import ArithmeticBrownianMotionUseCase
from estocasticos.use_cases.modelo_reversao_media_use_case import ReversaoMediaUseCase
from estocasticos.use_cases.random_walk_use_case import RandomWalkUseCase
from financial_options.models import FinantialModels, FinantialModelsChoices as Choices
from financial_options.report_registry import REGISTRY


def form_data(model_type, **overrides):
    """The screen's defaults as the form posts them."""
    defaults = dict(REGISTRY[model_type].defaults)
    if model_type == Choices.MARKOV_CHAIN:
        data = {
            'num_states': defaults['num_states'],
            'states': ', '.join(defaults['states']),
            'iterations': defaults['iterations'],
        }
        for i, row in enumerate(defaults['transition_matrix']):
            for j, value in enumerate(row):
                data[f'transition_matrix[{i}][{j}]'] = value
        for i, value in enumerate(defaults['initial_percentages']):
            data[f'initial_percentages[{i}]'] = value
    else:
        data = defaults
    return {**data, **overrides}


# url name of the calculation, model type of its screen, keys every answer has
CALCULATIONS = [
    ('simulate_markov', Choices.MARKOV_CHAIN, ('plot', 'evolution', 'states')),
    ('simulate_random_walk', Choices.RANDOM_WALK, ('plot_image', 'statistics', 'seed')),
    ('simulate_random_walk_normal', Choices.RANDOM_WALK_NORMAL, ('walk_plot', 'histograms_plot', 'statistics', 'seed')),
    ('abm_simulator', Choices.ARITHMETIC_BROWNIAN_MOTION, ('paths_plot', 'distribution_plot', 'statistics', 'seed')),
    ('monte_carlos_simulator', Choices.GBM_MONTE_CARLO, ('price_plot', 'convergence_plot', 'stats_descriptive', 'seed')),
    ('mbg_simulator', Choices.GBM_ITO, ('paths_plot', 'distribution_plot', 'statistics', 'seed')),
    ('simulate_mean_reversion', Choices.MEAN_REVERSION, ('paths_plot', 'distribution_plot', 'statistics', 'seed')),
    ('comparacao_modelos_view', Choices.MODELS_COMPARISON, ('plot_image', 'final_values', 'seed')),
]


class CalculationTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ana', password='secret')
        self.client.force_login(self.user)

    def set_language(self, language):
        session = self.client.session
        session['language'] = language
        session.save()


class CalculationEndpointTests(CalculationTestCase):
    def test_every_calculation_answers_the_screen_defaults(self):
        for url_name, model_type, keys in CALCULATIONS:
            with self.subTest(url_name=url_name):
                response = self.client.post(reverse(url_name), form_data(model_type))
                self.assertEqual(response.status_code, 200, response.content[:300])
                for key in keys:
                    self.assertIn(key, response.json())

    def test_calculations_need_login_and_post(self):
        for url_name, model_type, _ in CALCULATIONS:
            with self.subTest(url_name=url_name):
                self.assertEqual(self.client.get(reverse(url_name)).status_code, 405)
                self.client.logout()
                response = self.client.post(reverse(url_name), form_data(model_type))
                self.assertEqual(response.status_code, 302)
                self.client.force_login(self.user)

    def test_the_same_seed_repeats_the_simulation(self):
        for url_name, model_type, _ in CALCULATIONS:
            if model_type == Choices.MARKOV_CHAIN:
                continue  # deterministic
            with self.subTest(url_name=url_name):
                first = self.client.post(reverse(url_name), form_data(model_type, seed='12345')).json()
                again = self.client.post(reverse(url_name), form_data(model_type, seed='12345')).json()
                self.assertEqual(first['seed'], 12345)
                self.assertEqual(first, again)

    def test_an_empty_seed_draws_one_and_returns_it(self):
        response = self.client.post(reverse('abm_simulator'), form_data(Choices.ARITHMETIC_BROWNIAN_MOTION, seed=''))
        seed = response.json()['seed']
        self.assertTrue(0 <= seed <= 2 ** 32 - 1)
        again = self.client.post(reverse('abm_simulator'), form_data(Choices.ARITHMETIC_BROWNIAN_MOTION, seed=str(seed)))
        self.assertEqual(again.json()['statistics'], response.json()['statistics'])

    def test_invalid_inputs_return_400_in_the_session_language(self):
        cases = [
            ('abm_simulator', Choices.ARITHMETIC_BROWNIAN_MOTION, {'n_simulations': '5000'}, 'entre 2 e 1000', 'between 2 and 1000'),
            ('abm_simulator', Choices.ARITHMETIC_BROWNIAN_MOTION, {'sigma': 'abc'}, 'informe um número', 'enter a number'),
            ('abm_simulator', Choices.ARITHMETIC_BROWNIAN_MOTION, {'dt': '0.00001'}, 'o máximo é 10000', 'the maximum is 10000'),
            ('mbg_simulator', Choices.GBM_ITO, {'seed': '-1'}, 'Semente deve estar entre', 'Seed must be between'),
            ('simulate_mean_reversion', Choices.MEAN_REVERSION, {'kappa': '200'}, 'κ·dt deve ser menor que 1', 'κ·dt must be less than 1'),
            ('monte_carlos_simulator', Choices.GBM_MONTE_CARLO, {'time_unit': 'Século'}, 'opção inválida', 'invalid option'),
            ('simulate_random_walk', Choices.RANDOM_WALK, {'steps': '0'}, 'entre 1 e 10000', 'between 1 and 10000'),
            ('simulate_random_walk_normal', Choices.RANDOM_WALK_NORMAL, {'paths': '2.5'}, 'número inteiro', 'whole number'),
            ('comparacao_modelos_view', Choices.MODELS_COMPARISON, {'dt': '5'}, 'não pode ser maior', 'cannot be greater'),
        ]
        for url_name, model_type, overrides, pt, en in cases:
            for language, message in (('pt', pt), ('en', en)):
                with self.subTest(url_name=url_name, overrides=overrides, language=language):
                    self.set_language(language)
                    response = self.client.post(reverse(url_name), form_data(model_type, **overrides))
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(message, response.json()['error'])

    def test_mean_reversion_validates_the_effective_grid_step(self):
        endpoints = [
            ('simulate_mean_reversion', Choices.MEAN_REVERSION, 'T', 'kappa'),
            ('comparacao_modelos_view', Choices.MODELS_COMPARISON, 't', 'kappa_mr'),
        ]
        cases = [
            (0.7, 1.4, 400),  # dt becomes 1: the requested product is safe, the actual one is not.
            (0.7, 1.0, 400),  # The effective product is exactly 1, which is excluded.
            (0.6, 1.8, 200),  # dt becomes 0.5: the requested product exceeds 1, the actual one is safe.
        ]
        for url_name, model_type, horizon_key, kappa_key in endpoints:
            for dt, kappa, status in cases:
                with self.subTest(url_name=url_name, dt=dt, kappa=kappa):
                    data = form_data(model_type, **{horizon_key: 1, 'dt': dt, kappa_key: kappa, 'seed': 1})
                    response = self.client.post(reverse(url_name), data)
                    self.assertEqual(response.status_code, status, response.content[:300])
                    if status == 400:
                        self.assertIn('passo efetivo da grade', response.json()['error'])
                    else:
                        self.assertEqual(response.json()['seed'], 1)

    def test_markov_checks_rows_names_and_initial_distribution(self):
        cases = [
            ({'transition_matrix[0][0]': '60'}, 'soma 90%; deve somar 100%'),
            ({'states': 'A, B'}, 'Informe 3 nomes de estados'),
            ({'states': 'A, A, B'}, 'devem ser diferentes'),
            ({'initial_percentages[1]': '20'}, 'somam 120%'),
            ({'iterations': '51'}, 'entre 1 e 50'),
        ]
        for overrides, message in cases:
            with self.subTest(overrides=overrides):
                response = self.client.post(reverse('simulate_markov'), form_data(Choices.MARKOV_CHAIN, **overrides))
                self.assertEqual(response.status_code, 400)
                self.assertIn(message, response.json()['error'])

    def test_markov_evolution_converges_to_the_stationary_distribution(self):
        data = form_data(Choices.MARKOV_CHAIN, num_states='2', states='Sol, Chuva', iterations='50')
        data = {key: value for key, value in data.items() if '[2]' not in key}
        data.update({'transition_matrix[0][0]': '90', 'transition_matrix[0][1]': '10',
                     'transition_matrix[1][0]': '50', 'transition_matrix[1][1]': '50',
                     'initial_percentages[0]': '0', 'initial_percentages[1]': '100'})
        evolution = self.client.post(reverse('simulate_markov'), data).json()['evolution']
        self.assertEqual(len(evolution), 51)
        np.testing.assert_allclose(evolution[-1], [5 / 6, 1 / 6], atol=1e-9)


class SimulatorTests(TestCase):
    def test_the_grid_has_T_over_dt_increments_and_ends_at_T(self):
        model = ArithmeticBrownianMotionUseCase(100, 0, 1, 0.3, 0.1, 4, seed=1)
        self.assertEqual(model.steps, 3)  # int(0.3 / 0.1) would give 2
        self.assertEqual(model.paths.shape, (4, 4))
        self.assertAlmostEqual(model.time[-1], 0.3)

    def test_simulated_moments_match_the_theory(self):
        abm = ArithmeticBrownianMotionUseCase(100, 2, 10, 1, 0.01, 1000, seed=1).statistics()
        self.assertAlmostEqual(abm['mean'], abm['mean_theoretical'], delta=1.0)  # 3 standard errors
        self.assertAlmostEqual(abm['std'], abm['std_theoretical'], delta=0.7)
        mr = ReversaoMediaUseCase(80, 100, 1, 5, 2, 0.01, 1000, seed=1).statistics()
        self.assertAlmostEqual(mr['mean'], mr['mean_theoretical'], delta=0.5)
        self.assertAlmostEqual(mr['std'], mr['std_theoretical'], delta=0.4)

    def test_random_walk_has_the_number_of_steps_asked_for(self):
        walk = RandomWalkUseCase(1000, seed=1)
        self.assertEqual(len(walk.walks['normal']), 1001)
        self.assertEqual(walk.walks['discrete'][0], 0)


class StochasticReportTests(CalculationTestCase):
    def create(self, model_type, parameters, results):
        return FinantialModels.objects.create(
            usuario=self.user, model_type=model_type, parameters=parameters, results=results, report='online')

    def test_statistics_are_labelled_in_the_report_language(self):
        response = self.client.post(reverse('monte_carlos_simulator'), form_data(Choices.GBM_MONTE_CARLO, seed='7'))
        data = response.json()
        simulation = self.create(Choices.GBM_MONTE_CARLO, {**form_data(Choices.GBM_MONTE_CARLO), 'seed': 7}, data)

        self.set_language('en')
        report = self.client.get(reverse('view_report', args=[simulation.id])).context
        self.assertIn('Mean return (%)', report['results'])
        self.assertEqual(report['parameters']['Time unit'], 'Year')
        self.assertEqual(report['parameters']['Seed'], 7)
        self.assertIn('Upper bound (95% CI)', report['nested_results']['Inferential statistics (mean and 95% CI)'])

        self.set_language('pt')
        report = self.client.get(reverse('view_report', args=[simulation.id])).context
        self.assertIn('Retorno médio (%)', report['results'])

    def test_markov_report_shows_matrix_and_evolution_tables(self):
        parameters = {'num_states': 2, 'states': ['Sol', 'Chuva'], 'transition_matrix': [[90, 10], [50, 50]],
                      'initial_percentages': [100, 0], 'iterations': 1}
        simulation = self.create(Choices.MARKOV_CHAIN, parameters, {'evolution': [[1, 0], [0.9, 0.1]]})
        report = self.client.get(reverse('view_report', args=[simulation.id])).context
        self.assertEqual(report['parameters'], {'Número de estados': 2, 'Número de iterações': 1})
        matrix, initial, evolution = report['tables']
        self.assertEqual(matrix['headers'], ['De \\ Para', 'Sol', 'Chuva'])
        self.assertEqual(matrix['rows'][0], ['Sol', '90,00%', '10,00%'])
        self.assertEqual(evolution['rows'][1], [1, '90,00%', '10,00%'])

    def test_rerun_fills_the_saved_seed_and_markov_matrix(self):
        simulation = self.create(Choices.GBM_ITO, {**REGISTRY[Choices.GBM_ITO].defaults, 'seed': 99}, {'statistics': {}})
        response = self.client.get(reverse('rerun_simulation', args=[simulation.id]))
        self.assertContains(response, 'id="seed" name="seed" min="0" max="4294967295" step="1" value="99"')

        parameters = {**REGISTRY[Choices.MARKOV_CHAIN].defaults, 'states': ['X', 'Y'], 'num_states': 2,
                      'transition_matrix': [[50, 50], [25, 75]], 'initial_percentages': [40, 60]}
        simulation = self.create(Choices.MARKOV_CHAIN, parameters, {'evolution': []})
        response = self.client.get(reverse('rerun_simulation', args=[simulation.id]))
        self.assertContains(response, 'value="X, Y"')
        self.assertContains(response, '"transition_matrix": [[50, 50], [25, 75]]')
