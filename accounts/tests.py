from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.contrib.messages import get_messages
from django.core import mail
from django.db import IntegrityError
from django.test import Client, TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .forms import CustomAuthenticationForm, CustomUserCreationForm

User = get_user_model()


class CustomUserManagerTest(TestCase):
    def test_create_user(self):
        """Test creating a regular user."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="password123"
        )
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("password123"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_without_email(self):
        """Test that creating a user without email raises ValueError."""
        with self.assertRaises(ValueError):
            User.objects.create_user(
                username="testuser", email="", password="password123"
            )

    def test_create_superuser(self):
        """Test creating a superuser."""
        user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="password123"
        )
        self.assertEqual(user.username, "admin")
        self.assertEqual(user.email, "admin@example.com")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)


class CustomUserTest(TestCase):
    def test_str_method(self):
        """Test the __str__ method returns the email."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="password123"
        )
        self.assertEqual(str(user), "test@example.com")


class CustomUserCreationFormTest(TestCase):
    def test_valid_form(self):
        """Test form is valid with correct data."""
        form_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password1": "securepassword123",
            "password2": "securepassword123",
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_form_password_mismatch(self):
        """Test form is invalid when passwords don't match."""
        form_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password1": "securepassword123",
            "password2": "differentpassword",
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_invalid_form_missing_email(self):
        """Test form is invalid without email."""
        form_data = {
            "username": "testuser",
            "password1": "password123",
            "password2": "password123",
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)


class CustomAuthenticationFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="securepassword123"
        )

    def test_valid_login(self):
        """Test form is valid with correct credentials."""
        form_data = {
            "username": "test@example.com",  # Email as username
            "password": "securepassword123",
        }
        form = CustomAuthenticationForm(request=None, data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_login_wrong_password(self):
        """Test form is invalid with wrong password."""
        form_data = {
            "username": "test@example.com",
            "password": "wrongpassword",
        }
        form = CustomAuthenticationForm(request=None, data=form_data)
        self.assertFalse(form.is_valid())


class AccountsViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="securepassword123"
        )

    def test_login_view_get(self):
        """Test GET request to login view."""
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")

    def test_login_view_post_success(self):
        """Test successful POST to login view."""
        response = self.client.post(
            reverse("login"),
            {
                "username": "test@example.com",
                "password": "securepassword123",
            },
        )
        self.assertRedirects(response, reverse("profile"))
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Welcome back, testuser!")

    def test_login_view_post_failure(self):
        """Test failed POST to login view."""
        response = self.client.post(
            reverse("login"),
            {
                "username": "test@example.com",
                "password": "wrongpassword",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")

    def test_logout_view(self):
        """Test logout view with POST request."""
        self.client.login(username="test@example.com", password="securepassword123")
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("index"))
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "You have been logged out.")

    def test_logout_view_get_not_allowed(self):
        """Test logout view returns 405 for GET request."""
        self.client.login(username="test@example.com", password="securepassword123")
        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 405)

    def test_profile_view_authenticated(self):
        """Test profile view for authenticated user."""
        self.client.login(username="test@example.com", password="securepassword123")
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/profile.html")

    def test_profile_view_unauthenticated(self):
        """Test profile view redirects for unauthenticated user."""
        response = self.client.get(reverse("profile"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('profile')}")

    def test_register_view_get(self):
        """Test GET request to register view."""
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/register.html")

    def test_register_view_post_success(self):
        """Test successful POST to register view."""
        response = self.client.post(
            reverse("register"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "password1": "securepassword123",
                "password2": "securepassword123",
            },
        )
        self.assertRedirects(response, reverse("login"))
        self.assertTrue(User.objects.filter(email="new@example.com").exists())
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            str(messages[0]), "Account created successfully! Please log in."
        )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="resetuser", email="reset@example.com", password="oldpassword123"
        )

    def test_password_reset_view_get(self):
        response = self.client.get(reverse("password_reset"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/password_reset.html")

    def test_password_reset_view_post_success(self):
        response = self.client.post(
            reverse("password_reset"), {"email": self.user.email}
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)

    def test_password_reset_view_post_invalid_email(self):
        response = self.client.post(
            reverse("password_reset"), {"email": "missing@example.com"}
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_confirm_valid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        reset_url = reverse("password_reset_confirm", args=[uid, token])

        # First GET redirects to session-based URL after validating token
        response = self.client.get(reset_url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/password_reset_confirm.html")

        # POST to the session-based URL (last URL in redirect chain)
        session_url = response.redirect_chain[-1][0]
        post_response = self.client.post(
            session_url,
            {
                "new_password1": "newsecurepassword123",
                "new_password2": "newsecurepassword123",
            },
        )
        self.assertRedirects(post_response, reverse("password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newsecurepassword123"))

    def test_password_reset_confirm_invalid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        reset_url = reverse("password_reset_confirm", args=[uid, "invalid-token"])
        response = self.client.get(reset_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/password_reset_confirm.html")
        self.assertFalse(response.context["validlink"])

    def test_password_reset_complete_view(self):
        response = self.client.get(reverse("password_reset_complete"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/password_reset_complete.html")


class AdminInterfaceTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="superpassword123"
        )
        self.regular_user = User.objects.create_user(
            username="regular", email="regular@example.com", password="regularpass123"
        )

    def test_admin_permissions_required(self):
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_admin_user_list(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:accounts_customuser_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.superuser.email)

    def test_admin_user_creation(self):
        self.client.force_login(self.superuser)
        add_url = reverse("admin:accounts_customuser_add")
        response = self.client.post(
            add_url,
            {
                "email": "created@example.com",
                "username": "createduser",
                "password1": "Adm1nPassw0rd!",
                "password2": "Adm1nPassw0rd!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="created@example.com").exists())

    def test_admin_user_edit(self):
        self.client.force_login(self.superuser)
        target_user = User.objects.create_user(
            username="editable", email="editable@example.com", password="temp12345"
        )
        change_url = reverse("admin:accounts_customuser_change", args=[target_user.pk])
        response = self.client.post(
            change_url,
            {
                "email": "editable-updated@example.com",
                "username": "editable-updated",
                "is_active": "on",
                "is_staff": "on",
                "is_superuser": "",
                "groups": [],
                "user_permissions": [],
                "password": target_user.password,
            },
        )
        self.assertEqual(response.status_code, 302)
        target_user.refresh_from_db()
        self.assertEqual(target_user.email, "editable-updated@example.com")
        self.assertTrue(target_user.is_staff)

    def test_admin_user_delete(self):
        self.client.force_login(self.superuser)
        target_user = User.objects.create_user(
            username="tobedeleted", email="delete@example.com", password="temp12345"
        )
        delete_url = reverse("admin:accounts_customuser_delete", args=[target_user.pk])
        response = self.client.post(delete_url, {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=target_user.pk).exists())


class EdgeCaseSecurityTests(TestCase):
    def test_duplicate_email_registration(self):
        User.objects.create_user(
            username="first", email="dup@example.com", password="password123"
        )
        form = CustomUserCreationForm(
            data={
                "username": "second",
                "email": "dup@example.com",
                "password1": "securepassword123",
                "password2": "securepassword123",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_duplicate_username_registration(self):
        User.objects.create_user(
            username="duplicate", email="unique@example.com", password="password123"
        )
        form = CustomUserCreationForm(
            data={
                "username": "duplicate",
                "email": "another@example.com",
                "password1": "securepassword123",
                "password2": "securepassword123",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)

    def test_special_characters_in_password(self):
        form = CustomUserCreationForm(
            data={
                "username": "specialchar",
                "email": "special@example.com",
                "password1": "pässw0rd!@#$",
                "password2": "pässw0rd!@#$",
            }
        )
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertTrue(user.check_password("pässw0rd!@#$"))

    def test_very_long_email(self):
        long_email = "user." + ("a" * 200) + "@example.com"
        form = CustomUserCreationForm(
            data={
                "username": "longemail",
                "email": long_email,
                "password1": "securepassword123",
                "password2": "securepassword123",
            }
        )
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.email, long_email)

    def test_sql_injection_attempt_username(self):
        injection_string = "test'); DROP TABLE accounts_customuser;--"
        response = self.client.post(
            reverse("register"),
            {
                "username": injection_string,
                "email": "safe@example.com",
                "password1": "securepassword123",
                "password2": "securepassword123",
            },
        )
        self.assertRedirects(response, reverse("login"))
        self.assertTrue(User.objects.filter(username=injection_string).exists())

    def test_csrf_token_required_for_post(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            reverse("login"),
            {"username": "any@example.com", "password": "password123"},
        )
        self.assertEqual(response.status_code, 403)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class IntegrationFlowTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_full_registration_to_profile_flow(self):
        register_response = self.client.post(
            reverse("register"),
            {
                "username": "flowuser",
                "email": "flow@example.com",
                "password1": "securepassword123",
                "password2": "securepassword123",
            },
        )
        self.assertRedirects(register_response, reverse("login"))

        login_response = self.client.post(
            reverse("login"),
            {"username": "flow@example.com", "password": "securepassword123"},
        )
        self.assertRedirects(login_response, reverse("profile"))

        profile_response = self.client.get(reverse("profile"))
        self.assertEqual(profile_response.status_code, 200)

    def test_register_login_logout_flow(self):
        self.client.post(
            reverse("register"),
            {
                "username": "cycleuser",
                "email": "cycle@example.com",
                "password1": "securepassword123",
                "password2": "securepassword123",
            },
        )

        self.client.post(
            reverse("login"),
            {"username": "cycle@example.com", "password": "securepassword123"},
        )

        logout_response = self.client.post(reverse("logout"))
        self.assertRedirects(logout_response, reverse("index"))

        profile_response = self.client.get(reverse("profile"))
        self.assertRedirects(
            profile_response, f"{reverse('login')}?next={reverse('profile')}"
        )

    def test_password_reset_flow_integration(self):
        User.objects.create_user(
            username="integrated",
            email="integrated@example.com",
            password="securepassword123",
        )

        reset_request = self.client.post(
            reverse("password_reset"), {"email": "integrated@example.com"}
        )
        self.assertRedirects(reset_request, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        self.assertIn("integrated@example.com", email.to)
        # Extract reset link
        reset_link = [line for line in email.body.splitlines() if "/reset/" in line][0]

        # Follow the redirect from token URL to session-based URL
        confirm_get = self.client.get(reset_link, follow=True)
        self.assertEqual(confirm_get.status_code, 200)
        session_url = confirm_get.redirect_chain[-1][0]

        # POST the new password to the session URL
        confirm_response = self.client.post(
            session_url,
            {
                "new_password1": "newintegratedpassword123",
                "new_password2": "newintegratedpassword123",
            },
        )
        self.assertRedirects(confirm_response, reverse("password_reset_complete"))
