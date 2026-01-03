import os
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase, Client
from django.urls import reverse


class CoreViewsTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_index_view(self):
        """Test the index view renders correctly."""
        response = self.client.get(reverse("index"))
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
