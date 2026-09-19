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
}

# Inputs whose value is one of a fixed set, so the report has to translate the value too.
CHOICE_KEYS = ('option_type', 'simulationType', 'strategyType')

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


class RerunViewTests(LoggedInTestCase):
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
                self.assertContains(response, 'saetoSaveProject({')
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
