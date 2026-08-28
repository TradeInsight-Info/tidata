"""Typed exceptions for the tidata API client."""


class APIError(Exception):
    """Base exception for all TradeInsight API errors."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class TickerNotFoundError(APIError):
    """Raised when the requested ticker symbol does not exist."""


class AuthenticationError(APIError):
    """Raised when the API key is missing, invalid, or expired."""


class RateLimitError(APIError):
    """Raised when the API rate limit has been exceeded."""


class InvalidParameterError(APIError):
    """Raised when a required or invalid parameter is supplied."""


class APIClosedError(APIError):
    """Raised when the backing API has been retired and answers 410 Gone.

    Terminal, unlike AuthenticationError: no key will work again, so a caller
    catching this should stop rather than prompt for another credential.
    """


_CODE_MAP: dict[str, type[APIError]] = {
    "TICKER_NOT_FOUND": TickerNotFoundError,
    "TICKER_REQUIRED": InvalidParameterError,
    "INVALID_TICKER": TickerNotFoundError,
    "UNAUTHORIZED": AuthenticationError,
    "FORBIDDEN": AuthenticationError,
    "INVALID_API_KEY": AuthenticationError,
    "API_KEY_REQUIRED": AuthenticationError,
    "RATE_LIMIT_EXCEEDED": RateLimitError,
    "TOO_MANY_REQUESTS": RateLimitError,
    "INVALID_DATE": InvalidParameterError,
    "INVALID_PARAMETER": InvalidParameterError,
    "DATE_REQUIRED": InvalidParameterError,
    # The beta data API closed on 2 September 2026. The server sends this code
    # with a 410 so an install from before the shutdown says why, instead of
    # failing as an auth problem the user cannot fix.
    "API_CLOSED": APIClosedError,
}


def from_code(code: str, message: str) -> APIError:
    """Return the most specific exception class for the given error code."""
    exc_class = _CODE_MAP.get(code.upper(), APIError)
    return exc_class(code, message)
