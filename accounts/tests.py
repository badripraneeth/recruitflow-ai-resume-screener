from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class CustomUserModelTests(TestCase):
    def test_create_recruiter_user(self):
        """Verify normal user creation creates a recruiter with is_staff=False."""
        user = User.objects.create_user(
            email='recruiter@example.com',
            password='StrongPassword123!',
            first_name='Jane',
            last_name='Doe'
        )
        self.assertEqual(user.email, 'recruiter@example.com')
        self.assertEqual(user.role, User.ROLE_RECRUITER)
        self.assertTrue(user.is_recruiter)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password('StrongPassword123!'))

    def test_create_superuser(self):
        """Verify create_superuser assigns admin role and staff/superuser permissions."""
        admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPassword123!'
        )
        self.assertEqual(admin_user.email, 'admin@example.com')
        self.assertEqual(admin_user.role, User.ROLE_ADMIN)
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)

    def test_recruiter_cannot_have_staff_privilege(self):
        """
        Specification: Recruiter cannot access Django Admin.
        Verifies that saving a recruiter user enforces is_staff=False and is_superuser=False.
        """
        user = User.objects.create_user(
            email='recruiter2@example.com',
            password='Password123!',
            role=User.ROLE_RECRUITER
        )
        user.is_staff = True
        user.is_superuser = True
        user.save()
        # CustomUser.save() strictly resets is_staff=False and is_superuser=False if role is recruiter
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)


class AuthenticationViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.recruiter = User.objects.create_user(
            email='recruiter@example.com',
            password='Password123!',
            first_name='John',
            last_name='Recruiter'
        )
        self.superuser = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPassword123!'
        )

    def test_register_creates_recruiter_and_redirects_to_dashboard(self):
        response = self.client.post(reverse('accounts:register'), {
            'first_name': 'Sarah',
            'last_name': 'Connor',
            'email': 'sarah@example.com',
            'password': 'SecurePassword456!',
            'confirm_password': 'SecurePassword456!',
        })
        # Redirects to dashboard after registration
        self.assertRedirects(response, reverse('dashboard'))
        created = User.objects.get(email='sarah@example.com')
        self.assertEqual(created.role, User.ROLE_RECRUITER)
        self.assertFalse(created.is_staff)

    def test_login_recruiter_redirects_to_dashboard(self):
        response = self.client.post(reverse('accounts:login'), {
            'email': 'recruiter@example.com',
            'password': 'Password123!',
        })
        self.assertRedirects(response, reverse('dashboard'))

    def test_unauthenticated_dashboard_access_redirects_to_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_recruiter_cannot_access_django_admin(self):
        """
        Specification:
        Recruiter: Cannot access Django Admin.
        """
        self.client.login(email='recruiter@example.com', password='Password123!')
        response = self.client.get('/admin/', follow=True)
        # Django admin requires is_staff. For non-staff, it redirects to the admin login page
        # with an error or prompt indicating access is not permitted.
        self.assertIn('/admin/login/', response.redirect_chain[0][0])
        # Verify recruiter cannot see admin dashboard
        self.assertNotContains(response, 'Site administration')

    def test_superuser_can_access_django_admin(self):
        """
        Specification:
        Superuser: Can access Django Admin.
        """
        self.client.login(email='admin@example.com', password='AdminPassword123!')
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Site administration')

    def test_admin_panel_link_visibility_in_layout(self):
        """
        Specification:
        Admin Panel should appear ONLY when request.user.is_superuser.
        """
        # 1. As recruiter: Admin Panel link must NOT appear
        self.client.login(email='recruiter@example.com', password='Password123!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Admin Panel')

        # 2. As superuser: Admin Panel link MUST appear
        self.client.login(email='admin@example.com', password='AdminPassword123!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Admin Panel')

    def test_logout_redirects_to_login(self):
        self.client.login(email='recruiter@example.com', password='Password123!')
        response = self.client.get(reverse('accounts:logout'))
        self.assertRedirects(response, reverse('accounts:login'))


class SessionSecurityTests(TestCase):
    """Verifies session expiration, rolling timeouts, and security settings."""

    def test_session_settings_configured(self):
        from django.conf import settings
        # Default 1 hour (3600 seconds)
        self.assertEqual(settings.SESSION_COOKIE_AGE, 3600)
        # Rolling session: resets timer on activity
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)
        # Expires on browser close
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        # Protected against XSS
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)

    def test_login_creates_secure_session_cookie(self):
        User.objects.create_user(
            email='session_user@test.com',
            password='Password123!'
        )
        client = Client()
        response = client.post(reverse('accounts:login'), {
            'email': 'session_user@test.com',
            'password': 'Password123!'
        })
        self.assertEqual(response.status_code, 302)
        from django.conf import settings
        session_cookie = client.cookies.get(settings.SESSION_COOKIE_NAME)
        self.assertIsNotNone(session_cookie)
        self.assertTrue(session_cookie['httponly'])

