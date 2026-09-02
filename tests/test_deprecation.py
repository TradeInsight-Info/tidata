"""The closed-API front door: a 410 must read as terminal, not as a bad key.

The beta data API stopped answering on 2 September 2026. Anyone still running
an old install gets one shot at understanding why, and these pin both halves of
that: the code the server sends, and the warning raised before any request.
"""

from __future__ import annotations

import warnings

import pytest
import responses

from tidata.tifinance import Ticker
from tidata.tifinance.exceptions import (
    APIClosedError,
    APIError,
    AuthenticationError,
    from_code,
)

_URL = "https://api.tradeinsight.info/trading-data/v1/ohlc"


def test_api_closed_maps_to_its_own_terminal_error():
    err = from_code("API_CLOSED", "The beta data API closed on 2 September 2026.")
    assert isinstance(err, APIClosedError)
    assert err.code == "API_CLOSED"


def test_api_closed_is_not_an_auth_error():
    """The distinction that matters: no credential fixes this, so a caller
    retrying with another key is doing something futile."""
    assert not isinstance(from_code("API_CLOSED", "x"), AuthenticationError)
    assert isinstance(from_code("API_CLOSED", "x"), APIError)


@responses.activate
def test_a_410_from_the_server_surfaces_as_APIClosedError():
    responses.add(
        responses.GET,
        _URL,
        json={"code": "API_CLOSED", "message": "Closed 2 September 2026. See TradeInsight Desk."},
        status=410,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        t = Ticker("AAPL", api_key="k")

    # raise_errors defaults to False, which swallows API errors into an empty
    # frame. A closed API must escape that: an empty DataFrame reads as "no data
    # for this ticker" and hides the only fact that matters.
    with pytest.raises(APIClosedError) as excinfo:
        t.history(start="2024-01-01", end="2024-01-05")
    assert "Desk" in excinfo.value.message


def test_constructing_a_client_warns_before_any_request_is_made():
    with pytest.warns(DeprecationWarning, match="410 Gone"):
        Ticker("AAPL", api_key="k")


def test_an_injected_transport_does_not_warn():
    """The test seam and anyone pointing at their own server are unaffected."""

    class FakeTransport:
        def fetch(self, path: str, params: dict) -> list:
            return []

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        Ticker("AAPL", api_key="k", transport=FakeTransport())
