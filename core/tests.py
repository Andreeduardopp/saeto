import json
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from core.navigation import PAGES, page_url
from financial_options.models import FinantialModels, FinantialModelsChoices


class NavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('navigation', password='navigation-test')
        cls.other = User.objects.create_user('other')
        cls.project = FinantialModels.objects.create(
            usuario=cls.user, model_type=FinantialModelsChoices.RETURN_VOLATILITY,
            parameters={'periods': 3, 'prices': [100, 105, 110]}, results={'mean_continuous': .01},
            report='online')

    def setUp(self):
        self.client.force_login(self.user)

    def test_catalogue_pages_render_full_shell_and_keep_legacy_fragments(self):
        for language in ['pt', 'en']:
            self.client.post(reverse('set_language'), {'language': language})
            for page in PAGES:
                with self.subTest(page=page.slug, language=language):
                    response = self.client.get(page_url(page))
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, 'id="main-content"')
                    self.assertContains(response, 'id="saetoNavigation"')
                    self.assertEqual(response.context['navigation']['key'], page.slug)
                    legacy = self.client.get(reverse(page.view))
                    self.assertEqual(legacy.status_code, 200)
                    self.assertNotContains(legacy, 'id="saetoNavigation"')

    def test_fragment_is_authenticated_json_and_language_keeps_destination(self):
        url = reverse('return_volatility_page')
        for language in ['pt', 'en']:
            self.client.post(reverse('set_language'), {'language': language})
            response = self.client.get(url, HTTP_X_SAETO_FRAGMENT='1')
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('id="returnVolatilityScreen"', data['html'])
            self.assertEqual(data['page']['lang'], language)
            self.assertEqual(data['page']['url'], url)
            full = self.client.get(url)
            self.assertContains(full, '<html lang="en">' if language == 'en' else '<html lang="pt-BR">')
        self.client.logout()
        response = self.client.get(url, HTTP_X_SAETO_FRAGMENT='1')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(parse_qs(urlparse(response.url).query)['next'], [url])

    def test_login_preserves_valid_next_and_rejects_external_destinations(self):
        url = reverse('return_volatility_page')
        self.client.logout()
        response = self.client.get(reverse('login-customizado'), {'next': url})
        self.assertContains(response, f'name="next" value="{url}"')
        for destination, expected in [(url, url), ('https://evil.example/x', '/home/'), ('//evil.example', '/home/')]:
            response = self.client.post(reverse('login-customizado'), {
                'username': 'navigation', 'password': 'navigation-test', 'next': destination})
            self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_project_pages_and_reports_enforce_ownership(self):
        url = reverse('project_page', args=[self.project.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['navigation']['project'], str(self.project.id))
        self.assertContains(response, 'id="returnVolatilityScreen"')
        self.client.force_login(self.other)
        for target in [url, reverse('view_report', args=[self.project.id]), reverse('rerun_simulation', args=[self.project.id])]:
            self.assertEqual(self.client.get(target).status_code, 404)
            self.assertEqual(self.client.get(target, HTTP_X_SAETO_FRAGMENT='1').status_code, 404)

    def test_only_registered_pages_can_be_loaded(self):
        self.assertEqual(self.client.get('/ferramentas/unknown/').status_code, 404)
        response = self.client.get(reverse('return_volatility_page'), {'url': 'https://evil.example'})
        self.assertContains(response, 'id="returnVolatilityScreen"')

    def test_saved_project_links_and_pagination_are_real(self):
        response = self.client.get(page_url(next(p for p in PAGES if p.slug == 'projetos')))
        self.assertContains(response, f'href="{reverse("project_page", args=[self.project.id])}"')
        self.assertContains(response, 'href="/opcoes/retorno-volatilidade/"')

    def test_logout_clears_tab_drafts_and_logs_out(self):
        response = self.client.get(reverse('custom-logout'))
        self.assertContains(response, "key.startsWith('saeto:draft:')")
        self.assertNotIn('_auth_user_id', self.client.session)
