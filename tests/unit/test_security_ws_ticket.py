# ============================================================
#  FOREMAN — tests/unit/test_security_ws_ticket.py
#  Zweck: WS-Ticket-Krypto (core/security): kurzlebiges, WS-scoped Ticket
#         (aud="ws"). decode_ws_token akzeptiert Session-JWT ODER WS-Ticket,
#         lehnt fremde aud ab; das WS-Ticket ist auf HTTP (decode_access_token)
#         NICHT gültig (Scope-Begrenzung); abgelaufenes Ticket wird abgelehnt.
#  Architektur-Einordnung: Unit-Test (kein DB), Quality-Gate §10.3.
# ============================================================
from __future__ import annotations

import jwt
import pytest

from foreman.config import Settings
from foreman.core.security import (
    WS_TICKET_AUDIENCE,
    create_access_token,
    create_ws_ticket,
    decode_access_token,
    decode_ws_token,
)


def test_create_ws_ticket_carries_subject_and_ws_audience(test_settings: Settings) -> None:
    ticket = create_ws_ticket("42", test_settings)
    payload = decode_ws_token(ticket, test_settings)
    assert payload["sub"] == "42"
    assert payload["aud"] == WS_TICKET_AUDIENCE


def test_decode_ws_token_accepts_session_jwt(test_settings: Settings) -> None:
    # Rückwärtskompatibel: ein normales Session-JWT (ohne aud) bleibt am WS gültig.
    session_jwt = create_access_token("7", test_settings)
    payload = decode_ws_token(session_jwt, test_settings)
    assert payload["sub"] == "7"


def test_decode_ws_token_rejects_foreign_audience(test_settings: Settings) -> None:
    token = create_access_token("7", test_settings, extra_claims={"aud": "other"})
    with pytest.raises(jwt.InvalidTokenError):
        decode_ws_token(token, test_settings)


def test_ws_ticket_is_not_valid_on_http(test_settings: Settings) -> None:
    # Scope-Begrenzung: das WS-Ticket darf NICHT für HTTP-Routen gelten.
    ticket = create_ws_ticket("42", test_settings)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(ticket, test_settings)


def test_expired_ws_ticket_is_rejected(test_settings: Settings) -> None:
    ticket = create_ws_ticket("42", test_settings, expires_seconds=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_ws_token(ticket, test_settings)
