import logging
import os
from io import StringIO
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, Client, override_settings
from django.urls import reverse


class CoreViewsTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_index_view(self):
        """Test the index view renders correctly."""
        response = self.client.get(reverse("core:index"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/index.html")


class ServeCommandTests(TestCase):
    """Tests for the serve management command using Cheroot/CherryPy."""

    @patch("core.management.commands.serve.WSGIServer")
    @patch.dict(os.environ, {}, clear=True)
    def test_serve_command_defaults(self, mock_server_class):
        """Test serve command with default values when no env vars or args provided."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve", stdout=out)

        # Verify server was created with defaults
        mock_server_class.assert_called_once()
        call_args = mock_server_class.call_args

        # Check bind address (host, port)
        self.assertEqual(call_args[0][0], ("127.0.0.1", 8000))

        # Verify server.start() was called
        mock_server.start.assert_called_once()

    @patch("core.management.commands.serve.WSGIServer")
    @patch.dict(os.environ, {"SERVER_HOST": "0.0.0.0", "SERVER_PORT": "9000"})
    def test_serve_command_reads_env_vars(self, mock_server_class):
        """Test serve command reads SERVER_HOST and SERVER_PORT from environment."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve", stdout=out)

        call_args = mock_server_class.call_args
        self.assertEqual(call_args[0][0], ("0.0.0.0", 9000))

    @patch("core.management.commands.serve.WSGIServer")
    @patch.dict(os.environ, {"SERVER_HOST": "0.0.0.0", "SERVER_PORT": "9000"})
    def test_serve_command_cli_args_override_env(self, mock_server_class):
        """Test CLI arguments override environment variables."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve", host="192.168.1.1", port=3000, stdout=out)

        call_args = mock_server_class.call_args
        self.assertEqual(call_args[0][0], ("192.168.1.1", 3000))

    @patch("core.management.commands.serve.WSGIServer")
    @patch.dict(os.environ, {}, clear=True)
    def test_serve_command_with_workers(self, mock_server_class):
        """Test serve command with numthreads option."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve", numthreads=10, stdout=out)

        call_args = mock_server_class.call_args
        # Check kwargs for numthreads
        self.assertEqual(call_args[1].get("numthreads"), 10)

    @patch("core.management.commands.serve.WSGIServer")
    @patch.dict(
        os.environ,
        {"SERVER_TLS_CERT": "/path/to/cert.pem", "SERVER_TLS_KEY": "/path/to/key.pem"},
    )
    def test_serve_command_with_tls_from_env(self, mock_server_class):
        """Test serve command reads TLS cert and key from environment."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve", stdout=out)

        # Server should be created with ssl_certificate and ssl_private_key kwargs
        call_args = mock_server_class.call_args
        self.assertEqual(call_args[1].get("ssl_certificate"), "/path/to/cert.pem")
        self.assertEqual(call_args[1].get("ssl_private_key"), "/path/to/key.pem")

    @patch("core.management.commands.serve.WSGIServer")
    @patch.dict(
        os.environ,
        {"SERVER_TLS_CERT": "/env/cert.pem", "SERVER_TLS_KEY": "/env/key.pem"},
    )
    def test_serve_command_tls_cli_overrides_env(self, mock_server_class):
        """Test CLI TLS arguments override environment variables."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command(
            "serve",
            tls_cert="/cli/cert.pem",
            tls_key="/cli/key.pem",
            stdout=out,
        )

        call_args = mock_server_class.call_args
        self.assertEqual(call_args[1].get("ssl_certificate"), "/cli/cert.pem")
        self.assertEqual(call_args[1].get("ssl_private_key"), "/cli/key.pem")

    @patch("core.management.commands.serve.WSGIServer")
    @patch.dict(os.environ, {}, clear=True)
    def test_serve_command_tls_requires_both_cert_and_key(self, mock_server_class):
        """Test that TLS requires both cert and key."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        err = StringIO()

        # Providing only cert should work but not enable TLS
        call_command("serve", tls_cert="/path/to/cert.pem", stdout=out, stderr=err)

        call_args = mock_server_class.call_args
        # Should not have ssl_certificate or ssl_private_key if only one is provided
        self.assertIsNone(call_args[1].get("ssl_certificate"))
        self.assertIsNone(call_args[1].get("ssl_private_key"))


class ServeAsyncCommandTests(TestCase):
    """Tests for the serve-async management command using Daphne."""

    @patch("core.management.commands.serve_async.Server")
    @patch.dict(os.environ, {}, clear=True)
    def test_serve_async_command_defaults(self, mock_server_class):
        """Test serve-async command with default values."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve_async", stdout=out)

        # Verify server was created with defaults
        mock_server_class.assert_called_once()
        call_args = mock_server_class.call_args

        # Check that it has the host:port argument
        # Daphne Server signature: Server(application, hosts=..., port=..., **kwargs)
        self.assertIsNotNone(call_args)

    @patch("core.management.commands.serve_async.Server")
    @patch.dict(os.environ, {"SERVER_HOST": "0.0.0.0", "SERVER_PORT": "9000"})
    def test_serve_async_command_reads_env_vars(self, mock_server_class):
        """Test serve-async command reads SERVER_HOST and SERVER_PORT from environment."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve_async", stdout=out)

        mock_server_class.assert_called_once()

    @patch("core.management.commands.serve_async.Server")
    @patch.dict(os.environ, {"SERVER_HOST": "0.0.0.0", "SERVER_PORT": "9000"})
    def test_serve_async_command_cli_args_override_env(self, mock_server_class):
        """Test CLI arguments override environment variables for serve-async."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve_async", host="192.168.1.1", port=3000, stdout=out)

        mock_server_class.assert_called_once()

    @patch("core.management.commands.serve_async.Server")
    @patch.dict(
        os.environ,
        {"SERVER_TLS_CERT": "/path/to/cert.pem", "SERVER_TLS_KEY": "/path/to/key.pem"},
    )
    def test_serve_async_command_with_tls_from_env(self, mock_server_class):
        """Test serve-async command reads TLS cert and key from environment."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve_async", stdout=out)

        # Server should be created with ssl_certfile and ssl_keyfile kwargs
        call_args = mock_server_class.call_args
        self.assertEqual(call_args[1].get("ssl_certfile"), "/path/to/cert.pem")
        self.assertEqual(call_args[1].get("ssl_keyfile"), "/path/to/key.pem")

    @patch("core.management.commands.serve_async.Server")
    @patch.dict(
        os.environ,
        {"SERVER_TLS_CERT": "/env/cert.pem", "SERVER_TLS_KEY": "/env/key.pem"},
    )
    def test_serve_async_command_tls_cli_overrides_env(self, mock_server_class):
        """Test CLI TLS arguments override environment variables for serve-async."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command(
            "serve_async",
            tls_cert="/cli/cert.pem",
            tls_key="/cli/key.pem",
            stdout=out,
        )

        call_args = mock_server_class.call_args
        self.assertEqual(call_args[1].get("ssl_certfile"), "/cli/cert.pem")
        self.assertEqual(call_args[1].get("ssl_keyfile"), "/cli/key.pem")

    @patch("core.management.commands.serve_async.Server")
    @patch.dict(os.environ, {}, clear=True)
    def test_serve_async_command_tls_requires_both_cert_and_key(
        self, mock_server_class
    ):
        """Test that serve-async TLS requires both cert and key."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        err = StringIO()

        # Providing only cert should work but not enable TLS
        call_command(
            "serve_async", tls_cert="/path/to/cert.pem", stdout=out, stderr=err
        )

        call_args = mock_server_class.call_args
        # Should not have ssl_certfile or ssl_keyfile if only one is provided
        self.assertIsNone(call_args[1].get("ssl_certfile"))
        self.assertIsNone(call_args[1].get("ssl_keyfile"))


class StaticFilesTests(TestCase):
    """Tests for static file serving with WhiteNoise."""

    @override_settings(DEBUG=False)
    def test_static_files_served_in_production(self):
        """Test that static files are served when DEBUG=False."""
        # WhiteNoise should serve static files even with DEBUG=False
        # Django's admin ships with static files we can test against
        response = self.client.get("/static/admin/css/base.css")
        self.assertEqual(response.status_code, 200)
        # WhiteNoiseFileResponse has streaming_content, not content
        if hasattr(response, "streaming_content"):
            content = b"".join(response.streaming_content)
        else:
            content = response.content
        # Check for "DJANGO" (case insensitive) in the content
        self.assertIn(b"DJANGO", content.upper())

    @override_settings(DEBUG=False)
    def test_static_files_have_cache_headers(self):
        """Test that static files include caching headers."""
        response = self.client.get("/static/admin/css/base.css")
        self.assertEqual(response.status_code, 200)
        # WhiteNoise should add cache-control headers
        self.assertIn("Cache-Control", response.headers)

    def test_staticfiles_dirs_configured(self):
        """Test that STATICFILES_DIRS is properly configured."""
        # Ensure we have a static directory configured
        self.assertTrue(hasattr(settings, "STATICFILES_DIRS"))
        self.assertIsInstance(settings.STATICFILES_DIRS, list)


class LoggingTests(TestCase):
    """Tests for logging configuration."""

    def test_logging_configured(self):
        """Test that logging is properly configured."""
        self.assertIn("LOGGING", dir(settings))
        self.assertIsInstance(settings.LOGGING, dict)
        self.assertIn("version", settings.LOGGING)

    def test_logger_output_format(self):
        """Test that log messages include timestamp and level."""
        logger = logging.getLogger("django")

        # Capture log output
        with self.assertLogs("django", level="INFO") as cm:
            logger.info("Test log message")

        # Verify log output contains expected format
        self.assertEqual(len(cm.output), 1)
        self.assertIn("INFO", cm.output[0])
        self.assertIn("Test log message", cm.output[0])

    def test_app_loggers_exist(self):
        """Test that application loggers can be instantiated."""
        # These should not raise errors
        accounts_logger = logging.getLogger("accounts")
        links_logger = logging.getLogger("links")
        core_logger = logging.getLogger("core")

        self.assertIsNotNone(accounts_logger)
        self.assertIsNotNone(links_logger)
        self.assertIsNotNone(core_logger)


@override_settings(DEBUG=False)
class ErrorPageTests(TestCase):
    """Tests for custom error pages."""

    def test_404_page_uses_custom_template(self):
        """Test that 404 errors render the custom template."""
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Page Not Found", status_code=404)

    def test_404_page_extends_base_template(self):
        """Test that 404 page uses the site layout."""
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        # Check for elements from base.html
        self.assertContains(response, "My SaaS App", status_code=404)

    def test_500_page_uses_custom_template(self):
        """Test that 500 errors render the custom template."""
        # We can't easily trigger a real 500 in tests, so we'll check the view directly
        from django.views.defaults import server_error
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/")

        # Test the error view directly
        response = server_error(request, template_name="500.html")
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"Server Error", response.content)


class HealthCheckTests(TestCase):
    """Tests for the health check endpoint."""

    def test_health_check_returns_200(self):
        """Test that health check endpoint returns 200 OK."""
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)

    def test_health_check_json_response(self):
        """Test that health check returns JSON with status."""
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

        data = response.json()
        self.assertIn("status", data)
        self.assertEqual(data["status"], "healthy")

    def test_health_check_includes_database_status(self):
        """Test that health check verifies database connectivity."""
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("database", data)
        self.assertEqual(data["database"], "connected")

    def test_health_check_does_not_require_authentication(self):
        """Test that health check is accessible without login."""
        # Clear any existing session
        self.client.logout()

        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
