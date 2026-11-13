"""Fail-closed connection policy for personal-PC database automation."""


def is_local_automation_database(url, environ):
    """Disallow libpq routing overrides before any connection or child process."""
    return (
        url.host in {"localhost", "127.0.0.1", "::1"}
        and url.database == "yunoball_local"
        and not url.query
        and not any(environ.get(name) for name in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE"))
    )
