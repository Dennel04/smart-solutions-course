"""Production WSGI entry point for the existing Lab 2 Flask application."""

from .app import create_app


app = create_app()
