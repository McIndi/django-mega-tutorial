from django.test import TestCase, Client
from django.contrib.auth import authenticate, get_user_model
from django.urls import reverse
from django.contrib.messages import get_messages

from .forms import CustomUserCreationForm, CustomAuthenticationForm
from .models import CustomUser

User = get_user_model()


class CustomUserManagerTest(TestCase):
    def test_create_user(self):
        """Test creating a regular user."""
        user = User.objects.create_user(username='testuser', email='test@example.com', password='password123')
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('password123'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_without_email(self):
        """Test that creating a user without email raises ValueError."""
        with self.assertRaises(ValueError):
            User.objects.create_user(username='testuser', email='', password='password123')

    def test_create_superuser(self):
        """Test creating a superuser."""
        user = User.objects.create_superuser(username='admin', email='admin@example.com', password='password123')
        self.assertEqual(user.username, 'admin')
        self.assertEqual(user.email, 'admin@example.com')
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)


class CustomUserTest(TestCase):
    def test_str_method(self):
        """Test the __str__ method returns the email."""
        user = User.objects.create_user(username='testuser', email='test@example.com', password='password123')
        self.assertEqual(str(user), 'test@example.com')


class CustomUserCreationFormTest(TestCase):
    def test_valid_form(self):
        """Test form is valid with correct data."""
        form_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password1': 'securepassword123',
            'password2': 'securepassword123',
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_form_password_mismatch(self):
        """Test form is invalid when passwords don't match."""
        form_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password1': 'securepassword123',
            'password2': 'differentpassword',
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)

    def test_invalid_form_missing_email(self):
        """Test form is invalid without email."""
        form_data = {
            'username': 'testuser',
            'password1': 'password123',
            'password2': 'password123',
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)


class CustomAuthenticationFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='securepassword123')
    def test_valid_login(self):
        """Test form is valid with correct credentials."""
        form_data = {
            'username': 'test@example.com',  # Email as username
            'password': 'securepassword123',
        }
        form = CustomAuthenticationForm(request=None, data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_login_wrong_password(self):
        """Test form is invalid with wrong password."""
        form_data = {
            'username': 'test@example.com',
            'password': 'wrongpassword',
        }
        form = CustomAuthenticationForm(request=None, data=form_data)
        self.assertFalse(form.is_valid())


class AccountsViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='securepassword123')

    def test_login_view_get(self):
        """Test GET request to login view."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')

    def test_login_view_post_success(self):
        """Test successful POST to login view."""
        response = self.client.post(reverse('login'), {
            'username': 'test@example.com',
            'password': 'securepassword123',
        })
        self.assertRedirects(response, reverse('profile'))
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'Welcome back, testuser!')

    def test_login_view_post_failure(self):
        """Test failed POST to login view."""
        response = self.client.post(reverse('login'), {
            'username': 'test@example.com',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')

    def test_logout_view(self):
        """Test logout view."""
        self.client.login(username='test@example.com', password='securepassword123')
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('index'))
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'You have been logged out.')

    def test_profile_view_authenticated(self):
        """Test profile view for authenticated user."""
        self.client.login(username='test@example.com', password='securepassword123')
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/profile.html')

    def test_profile_view_unauthenticated(self):
        """Test profile view redirects for unauthenticated user."""
        response = self.client.get(reverse('profile'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('profile')}")

    def test_register_view_get(self):
        """Test GET request to register view."""
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/register.html')

    def test_register_view_post_success(self):
        """Test successful POST to register view."""
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'new@example.com',
            'password1': 'securepassword123',
            'password2': 'securepassword123',
        })
        self.assertRedirects(response, reverse('login'))
        self.assertTrue(User.objects.filter(email='new@example.com').exists())
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'Account created successfully! Please log in.')
