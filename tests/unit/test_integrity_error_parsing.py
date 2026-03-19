"""Tests for _integrity_error_to_field_errors in views.dynamic module."""

from sqlalchemy.exc import IntegrityError

from hyperadmin.views.dynamic import _integrity_error_to_field_errors


def _make_integrity_error(message: str) -> IntegrityError:
    """Create an IntegrityError with a given original exception message."""
    orig = Exception(message)
    exc = IntegrityError("", {}, orig)
    return exc


def test_sqlite_unique_constraint():
    exc = _make_integrity_error("UNIQUE constraint failed: users.username")
    result = _integrity_error_to_field_errors(exc)
    assert result == {"username": "Username already exists."}


def test_sqlite_unique_constraint_underscore_field():
    exc = _make_integrity_error("UNIQUE constraint failed: users.email_address")
    result = _integrity_error_to_field_errors(exc)
    assert result == {"email_address": "Email Address already exists."}


def test_postgresql_unique_constraint():
    exc = _make_integrity_error(
        'duplicate key value violates unique constraint "users_username_key"'
    )
    result = _integrity_error_to_field_errors(exc)
    assert result == {"username": "Username already exists."}


def test_postgresql_unique_constraint_compound_table_name():
    exc = _make_integrity_error(
        'duplicate key value violates unique constraint "user_groups_name_key"'
    )
    result = _integrity_error_to_field_errors(exc)
    assert result == {"groups_name": "Groups Name already exists."}


def test_unrecognized_message_returns_generic_error():
    exc = _make_integrity_error("some other database error")
    result = _integrity_error_to_field_errors(exc)
    assert result == {"__all__": "A record with these values already exists."}


def test_no_orig_falls_back_to_str():
    exc = IntegrityError("UNIQUE constraint failed: t.name", {}, None)
    result = _integrity_error_to_field_errors(exc)
    assert result == {"name": "Name already exists."}
