"""
Management command to serve Django async with Daphne (ASGI server).

Supports TLS and other options. Suitable for applications using async views or WebSockets.
This command allows testing async compatibility even when not actively using WebSockets.
"""

import logging
import os
import sys

from daphne.server import Server
from django.core.asgi import get_asgi_application
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Serve Django application using Daphne (ASGI server) for async support"

    def add_arguments(self, parser):
        """Define command-line arguments with defaults from environment variables."""
        parser.add_argument(
            "--host",
            default=os.getenv("SERVER_HOST", "127.0.0.1"),
            help="Host to bind to (default: SERVER_HOST env var or 127.0.0.1)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=int(os.getenv("SERVER_PORT", "8000")),
            help="Port to bind to (default: SERVER_PORT env var or 8000)",
        )
        parser.add_argument(
            "--tls-cert",
            default=os.getenv("SERVER_TLS_CERT"),
            help="Path to TLS certificate file (default: SERVER_TLS_CERT env var)",
        )
        parser.add_argument(
            "--tls-key",
            default=os.getenv("SERVER_TLS_KEY"),
            help="Path to TLS private key file (default: SERVER_TLS_KEY env var)",
        )

    def handle(self, *args, **options):
        """Start the Daphne ASGI server."""
        host = options["host"]
        port = options["port"]
        tls_cert = options["tls_cert"]
        tls_key = options["tls_key"]

        # Get the ASGI application
        application = get_asgi_application()

        # Build server kwargs
        server_kwargs = {}

        # Enable TLS only if both cert and key are provided
        if tls_cert and tls_key:
            server_kwargs["ssl_certfile"] = tls_cert
            server_kwargs["ssl_keyfile"] = tls_key
            protocol = "https"
            self.stdout.write(
                self.style.SUCCESS(f"TLS enabled (cert: {tls_cert}, key: {tls_key})")
            )
        else:
            protocol = "http"
            if tls_cert or tls_key:
                self.stdout.write(
                    self.style.WARNING(
                        "TLS not enabled: both --tls-cert and --tls-key are required"
                    )
                )

        server = Server(
            application,
            endpoints=[f"tcp:{port}:interface={host}"],
            signal_handlers=True,
            **server_kwargs,
        )

        logger.info(f"Starting Daphne ASGI server on {protocol}://{host}:{port}/")

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting Daphne ASGI server on {protocol}://{host}:{port}/"
            )
        )
        self.stdout.write("Quit the server with CONTROL-C.")

        try:
            server.run()
        except KeyboardInterrupt:
            logger.info("Shutting down server...")
            self.stdout.write(self.style.SUCCESS("\nShutting down server..."))
            sys.exit(0)
