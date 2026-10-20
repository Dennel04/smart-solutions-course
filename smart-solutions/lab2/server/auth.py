"""Authentication helpers for the user and Atom API boundaries."""

from functools import wraps
import hmac

from flask import current_app, jsonify, make_response, render_template, request


def _error(status, code, message, headers=None):
    response = jsonify(error={"code": code, "message": message})
    response.status_code = status
    if headers:
        response.headers.update(headers)
    return response


def user_auth_required(view):
    """Require HTTP Basic auth for the post-office user surface."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        auth = request.authorization
        username = current_app.config["USER_USERNAME"]
        password = current_app.config["USER_PASSWORD"]
        if auth is None:
            return _user_error(
                401,
                "user_auth_required",
                "User authentication is required.",
                {"WWW-Authenticate": 'Basic realm="Lab 2 post-office"'},
            )
        valid = hmac.compare_digest(auth.username or "", username) and hmac.compare_digest(
            auth.password or "", password
        )
        if not valid:
            return _user_error(
                401,
                "invalid_user_credentials",
                "Invalid user credentials.",
                {"WWW-Authenticate": 'Basic realm="Lab 2 post-office"'},
            )
        return view(*args, **kwargs)

    return wrapped


def _user_error(status, code, message, headers):
    # Only the browser page/form gets HTML. API error contracts stay unchanged.
    if request.path in {"/", "/jobs"}:
        response = make_response(render_template("unauthorized.html"), status)
        response.headers.update(headers)
        return response
    return _error(status, code, message, headers)


def atom_auth_required(view):
    """Require the configured bearer key for Atom-only endpoints."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return _error(401, "atom_key_required", "Atom bearer key is required.")
        supplied = header[len("Bearer ") :]
        expected = current_app.config["ATOM_API_KEY"]
        if not hmac.compare_digest(supplied, expected):
            return _error(403, "invalid_atom_key", "Atom bearer key is invalid.")
        return view(*args, **kwargs)

    return wrapped
