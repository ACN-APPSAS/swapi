"""
SWAPI web view test suite.

Run with: SECRET_KEY=test-secret python manage.py test
"""
from __future__ import unicode_literals

from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase


# ── Public Web Views ──────────────────────────────────────────────────────────

class IndexViewTests(TestCase):
    def test_returns_200(self):
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_uses_index_template(self):
        response = self.client.get('/')
        self.assertTemplateUsed(response, 'index.html')

    def test_uses_base_template(self):
        response = self.client.get('/')
        self.assertTemplateUsed(response, 'base.html')

    def test_stripe_key_in_context(self):
        response = self.client.get('/')
        self.assertIn('stripe_key', response.context)


class DocumentationViewTests(TestCase):
    def test_returns_200(self):
        self.assertEqual(self.client.get('/documentation').status_code, 200)

    def test_uses_documentation_template(self):
        response = self.client.get('/documentation')
        self.assertTemplateUsed(response, 'documentation.html')


class AboutViewTests(TestCase):
    def test_returns_200(self):
        self.assertEqual(self.client.get('/about').status_code, 200)

    def test_uses_about_template(self):
        response = self.client.get('/about')
        self.assertTemplateUsed(response, 'about.html')

    def test_stripe_key_in_context(self):
        response = self.client.get('/about')
        self.assertIn('stripe_key', response.context)

    def test_resource_counts_in_context(self):
        response = self.client.get('/about')
        for key in ('people', 'planets', 'films', 'species', 'vehicles', 'starships'):
            self.assertIn(key, response.context)

    def test_second_request_uses_cache(self):
        # Both requests should succeed; cache is transparent to the caller
        r1 = self.client.get('/about')
        r2 = self.client.get('/about')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)


# ── Stats View (login_required) ───────────────────────────────────────────────

class StatsViewTests(TestCase):
    def test_unauthenticated_redirects(self):
        response = self.client.get('/stats')
        self.assertEqual(response.status_code, 302)

    def test_unauthenticated_redirect_target_contains_login(self):
        response = self.client.get('/stats')
        self.assertIn('login', response['Location'])

    def test_unauthenticated_redirect_contains_next_param(self):
        response = self.client.get('/stats')
        self.assertIn('next', response['Location'])

    def test_authenticated_returns_200(self):
        user = User.objects.create_user('statsuser', password='pw')
        self.client.force_login(user)
        response = self.client.get('/stats')
        self.assertEqual(response.status_code, 200)

    def test_authenticated_uses_stats_template(self):
        user = User.objects.create_user('statsuser2', password='pw')
        self.client.force_login(user)
        response = self.client.get('/stats')
        self.assertTemplateUsed(response, 'stats.html')

    def test_authenticated_keen_project_id_in_context(self):
        user = User.objects.create_user('statsuser3', password='pw')
        self.client.force_login(user)
        response = self.client.get('/stats')
        self.assertIn('keen_project_id', response.context)

    def test_keen_read_key_not_in_context(self):
        # keen_read_key must not be exposed to the template (P2 security fix)
        user = User.objects.create_user('statsuser4', password='pw')
        self.client.force_login(user)
        response = self.client.get('/stats')
        self.assertNotIn('keen_read_key', response.context)


# ── Stripe Donation View ──────────────────────────────────────────────────────

class StripeDonationViewTests(TestCase):
    """
    stripe.Customer.create and stripe.Charge.create are mocked throughout
    to prevent real API calls and isolate view logic.
    """

    STRIPE_CUSTOMER_PATH = 'swapi.views.stripe.Customer.create'
    STRIPE_CHARGE_PATH = 'swapi.views.stripe.Charge.create'

    def test_get_redirects_to_home(self):
        response = self.client.get('/stripe/donation')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/')

    @patch('swapi.views.stripe.Customer.create')
    @patch('swapi.views.stripe.Charge.create')
    def test_post_redirects_to_home(self, mock_charge, mock_customer):
        mock_customer.return_value = MagicMock(id='cus_test')
        mock_charge.return_value = MagicMock(id='ch_test')
        response = self.client.post('/stripe/donation', {
            'stripeToken': 'tok_test',
            'stripeEmail': 'donor@example.com',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/')

    @patch('swapi.views.stripe.Customer.create')
    @patch('swapi.views.stripe.Charge.create')
    def test_post_calls_customer_create_with_email_and_source(
        self, mock_charge, mock_customer
    ):
        mock_customer.return_value = MagicMock(id='cus_abc')
        mock_charge.return_value = MagicMock(id='ch_abc')
        self.client.post('/stripe/donation', {
            'stripeToken': 'tok_visa',
            'stripeEmail': 'test@example.com',
        })
        mock_customer.assert_called_once_with(
            email='test@example.com',
            source='tok_visa',
        )

    @patch('swapi.views.stripe.Customer.create')
    @patch('swapi.views.stripe.Charge.create')
    def test_post_calls_charge_create_with_fixed_amount(
        self, mock_charge, mock_customer
    ):
        mock_customer.return_value = MagicMock(id='cus_xyz')
        mock_charge.return_value = MagicMock(id='ch_xyz')
        self.client.post('/stripe/donation', {
            'stripeToken': 'tok_test',
            'stripeEmail': 'donor@example.com',
        })
        mock_charge.assert_called_once_with(
            customer='cus_xyz',
            amount=1000,  # fixed at $10.00 in cents
            currency='usd',
            description='SWAPI donation',
        )

    @patch('swapi.views.stripe.Customer.create')
    @patch('swapi.views.stripe.Charge.create', side_effect=Exception('Card declined'))
    def test_post_with_failed_charge_still_redirects(self, mock_charge, mock_customer):
        mock_customer.return_value = MagicMock(id='cus_fail')
        response = self.client.post('/stripe/donation', {
            'stripeToken': 'tok_fail',
            'stripeEmail': 'donor@example.com',
        })
        # charge failure is silently swallowed; redirect must still happen
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/')

    @patch('swapi.views.stripe.Customer.create')
    @patch('swapi.views.stripe.Charge.create')
    def test_post_with_missing_token_sends_empty_string(
        self, mock_charge, mock_customer
    ):
        mock_customer.return_value = MagicMock(id='cus_empty')
        mock_charge.return_value = MagicMock(id='ch_empty')
        response = self.client.post('/stripe/donation', {
            'stripeEmail': 'donor@example.com',
        })
        mock_customer.assert_called_once_with(email='donor@example.com', source='')
        self.assertEqual(response.status_code, 302)

    @patch('swapi.views.stripe.Customer.create')
    @patch('swapi.views.stripe.Charge.create')
    def test_post_with_missing_email_sends_empty_string(
        self, mock_charge, mock_customer
    ):
        mock_customer.return_value = MagicMock(id='cus_noemail')
        mock_charge.return_value = MagicMock(id='ch_noemail')
        self.client.post('/stripe/donation', {'stripeToken': 'tok_test'})
        mock_customer.assert_called_once_with(email='', source='tok_test')

    def test_endpoint_enforces_csrf(self):
        # CSRF protection must be active on the payment endpoint (P1 security fix)
        client = self.client_class(enforce_csrf_checks=True)
        response = client.post('/stripe/donation', {
            'stripeToken': 'tok_test',
            'stripeEmail': 'donor@example.com',
        })
        self.assertEqual(response.status_code, 403)
