from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from teoria_dos_jogos.use_cases.dilema_prisioneiro_use_case import (
    HISTORY_PAGE_SIZE, MAX_ITERATIONS, STRATEGIES, DilemaPrisioneiroUseCase,
)


class DilemaPrisioneiroViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ana', password='secret')
        self.client.force_login(self.user)
        self.url = reverse('dilema_do_prisioneiro')

    def set_language(self, language):
        session = self.client.session
        session['language'] = language
        session.save()

    def post(self, **overrides):
        data = {'strategy1': 'tit_for_tat', 'strategy2': 'always_defect', 'iterations': '10'}
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_anonymous_request_is_redirected_to_login(self):
        self.client.logout()
        response = self.client.post(self.url, {'iterations': '10'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])

    def test_a_valid_run_returns_one_move_per_player_per_round(self):
        response = self.post(iterations='7')
        self.assertEqual(response.status_code, 200)
        result = response.json()['result']
        self.assertEqual(len(result['history1']), 7)
        self.assertEqual(len(result['history2']), 7)
        self.assertEqual(response.json()['iterations'], 7)
        self.assertIsInstance(result['payoff1'], int)
        self.assertIsInstance(result['payoff2'], int)

    def test_the_limits_of_the_screen_are_the_limits_of_the_server(self):
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn(f'max="{MAX_ITERATIONS}"', content)
        self.assertIn('min="1"', content)
        # The screen names the limit the way the message does.
        self.assertIn('De 1 a 1.000 rodadas', content)
        self.set_language('en')
        self.assertIn('From 1 to 1,000 rounds',
                      self.client.get(self.url).content.decode())
        self.assertEqual(self.post(iterations=str(MAX_ITERATIONS)).status_code, 200)
        self.assertEqual(self.post(iterations=str(MAX_ITERATIONS + 1)).status_code, 400)

    def test_an_iteration_count_that_is_not_a_whole_number_in_range_is_refused(self):
        for value in ('', '   ', 'dez', '0', '-5', '10.5', 'NaN', 'Infinity', str(MAX_ITERATIONS + 1)):
            with self.subTest(iterations=value):
                response = self.post(iterations=value)
                self.assertEqual(response.status_code, 400, value)
                self.assertTrue(response.json()['error'])
                self.assertNotIn('result', response.json())

    def test_a_missing_or_unknown_strategy_is_refused(self):
        for overrides in ({'strategy1': 'sempre_trair'}, {'strategy2': ''}, {'strategy1': None}):
            with self.subTest(overrides=overrides):
                data = {'strategy1': 'tit_for_tat', 'strategy2': 'always_defect', 'iterations': '10'}
                data.update({k: v for k, v in overrides.items() if v is not None})
                for key, value in overrides.items():
                    if value is None:
                        data.pop(key)
                response = self.client.post(self.url, data)
                self.assertEqual(response.status_code, 400)

    def test_every_offered_strategy_is_accepted_against_every_other(self):
        for strategy1 in STRATEGIES:
            for strategy2 in STRATEGIES:
                with self.subTest(strategy1=strategy1, strategy2=strategy2):
                    response = self.post(strategy1=strategy1, strategy2=strategy2, iterations='4')
                    self.assertEqual(response.status_code, 200)

    def test_the_screen_offers_exactly_the_strategies_the_server_accepts(self):
        content = self.client.get(self.url).content.decode()
        for strategy in STRATEGIES:
            self.assertIn(f'value="{strategy}"', content)
        self.assertEqual(content.count('<option value="'), 2 * len(STRATEGIES))

    def test_the_message_follows_the_language_of_the_session(self):
        for language, expected in (('pt', 'Iterações deve estar entre 1 e 1.000.'),
                                   ('en', 'Iterations must be between 1 and 1,000.')):
            with self.subTest(language=language):
                self.set_language(language)
                response = self.post(iterations='0')
                self.assertEqual(response.json()['error'], expected)

    def test_the_screen_renders_the_history_one_page_at_a_time(self):
        content = self.client.get(self.url).content.decode()
        self.assertIn('historyBody', content)
        self.assertIn(f"Number('{HISTORY_PAGE_SIZE}')", content)
        # The rounds are built by the screen, not printed into the page.
        self.assertNotIn('forloop.counter', content)

    def test_the_screen_installs_one_listener_on_its_own_form(self):
        content = self.client.get(self.url).content.decode()
        self.assertIn("form.addEventListener('submit'", content)
        self.assertNotIn("document.addEventListener('submit'", content)


class DilemaPrisioneiroUseCaseTests(TestCase):
    def test_tit_for_tat_opens_cooperating_and_then_repeats_the_opponent(self):
        result = DilemaPrisioneiroUseCase('tit_for_tat', 'always_defect', 3).run_simulation()
        self.assertEqual(result['history1'], ['cooperate', 'defect', 'defect'])
        self.assertEqual(result['history2'], ['defect', 'defect', 'defect'])
        # 0 + 1 + 1 against 5 + 1 + 1.
        self.assertEqual((result['payoff1'], result['payoff2']), (2, 7))

    def test_mutual_cooperation_scores_three_a_round(self):
        result = DilemaPrisioneiroUseCase('always_cooperate', 'always_cooperate', 5).run_simulation()
        self.assertEqual((result['payoff1'], result['payoff2']), (15, 15))

    def test_an_unknown_strategy_is_a_programming_error_not_a_silent_round(self):
        with self.assertRaises(ValueError):
            DilemaPrisioneiroUseCase('sempre_trair', 'always_defect', 1).run_simulation()
