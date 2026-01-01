"""
Management command to serve Django with Cheroot (CherryPy's production-grade WSGI server).

Supports TLS and configurable threading. Suitable for production use.
"""

import os
import sys

from cheroot.wsgi import Server as WSGIServer
from django.core.management.base import BaseCommand
from django.core.wsgi import get_wsgi_application


class Command(BaseCommand):
    help = "Serve Django application using Cheroot (CherryPy WSGI server)"

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
            "--numthreads",
            type=int,
            default=int(os.getenv("SERVER_NUMTHREADS", "10")),
            help="Number of threads for handling requests (default: SERVER_NUMTHREADS env var or 10)",
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
        """Start the Cheroot WSGI server."""
        host = options["host"]
        port = options["port"]
        numthreads = options["numthreads"]
        tls_cert = options["tls_cert"]
        tls_key = options["tls_key"]

        # Get the WSGI application
        application = get_wsgi_application()

        # Build server kwargs
        server_kwargs = {"numthreads": numthreads}

        # Enable TLS only if both cert and key are provided
        if tls_cert and tls_key:
            server_kwargs["ssl_certificate"] = tls_cert
            server_kwargs["ssl_private_key"] = tls_key
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

        # Create and configure server
        server = WSGIServer((host, port), application, **server_kwargs)

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting Cheroot WSGI server on {protocol}://{host}:{port}/"
            )
        )
        self.stdout.write(f"Number of threads: {numthreads}")
        self.stdout.write("Quit the server with CONTROL-C.")

        try:
            server.start()
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS("\nShutting down server..."))
            server.stop()
            sys.exit(0)
