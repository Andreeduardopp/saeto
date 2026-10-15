"""Part 6: the JS screen's actual save payload crosses the Django boundary."""
import json
import math
import shutil
import statistics
import subprocess
from pathlib import Path
from unittest import skipUnless

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from financial_options.models import FinantialModels

ROOT = Path(__file__).resolve().parents[1]


@skipUnless(shutil.which('node'), 'Node is required for the screen-to-Django integration test')
class ActivityAcceptanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('activity')
        self.client.force_login(self.user)

    def test_import_calculate_annualize_copy_save_report_rerun(self):
        for lang in ('pt', 'en'):
            for count in (9, 300, 1000):
                with self.subTest(lang=lang, count=count):
                    bridge = subprocess.run(
                        ['node', str(ROOT / 'tests/js/acceptance_payload.cjs'), lang, str(count)],
                        cwd=ROOT, check=True, capture_output=True, text=True, encoding='utf-8', timeout=30)
                    screen = json.loads(bridge.stdout)
                    payload = screen['payload']
                    parameters, results = payload['parameters'], payload['results']
                    # Independent reference from the full-precision prices, not rounded report values.
                    prices = parameters['prices']
                    returns = [math.log(right / left) for left, right in zip(prices, prices[1:])]
                    self.assertAlmostEqual(results['mean_continuous'], statistics.mean(returns), delta=1e-14)
                    self.assertAlmostEqual(results['volatility_continuous'], statistics.stdev(returns), delta=1e-14)
                    self.assertAlmostEqual(results['annual_rate_equivalent'], math.expm1(252 * statistics.mean(returns)), delta=1e-12)
                    self.assertAlmostEqual(results['annual_volatility_continuous'], math.sqrt(252) * statistics.stdev(returns), delta=1e-12)
                    self.assertEqual(len(screen['tsv'].split('\r\n')[1:count + 1]), count)
                    self.assertIn(screen['mean'], screen['tsv'])
                    self.assertIn(screen['annual'], screen['tsv'])
                    self.client.post(reverse('set_language'), {'language': lang})
                    response = self.client.post(reverse('save_financial_model'), data=json.dumps({
                        'name': f'Acceptance {count} {lang}', 'model_type': payload['modelType'],
                        'parameters': parameters, 'results': results,
                    }), content_type='application/json')
                    self.assertEqual(response.status_code, 200)
                    saved = response.json()
                    model = FinantialModels.objects.get(pk=saved['id'])
                    self.assertEqual(model.parameters, parameters)
                    self.assertEqual(model.results, results)
                    report = self.client.get(saved['report_url'])
                    self.assertEqual(report.status_code, 200)
                    self.assertContains(report, screen['mean'])
                    self.assertContains(report, screen['annual'])
                    rerun = self.client.get(reverse('project_page', args=[model.id]))
                    self.assertEqual(rerun.status_code, 200)
                    self.assertContains(rerun, 'id="saetoNavigation"')
                    self.assertEqual(rerun.context['initial_data']['prices'], prices)
                    self.assertEqual(rerun.context['initial_data']['periodsPerYear'], 252)
                    self.assertEqual(rerun.context['navigation']['project'], str(model.id))
