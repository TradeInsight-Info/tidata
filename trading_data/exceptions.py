"""Typed exceptions for Trading Data Service API error codes."""


class APIError(Exception):
    """Base exception for all Trading Data Service API errors."""

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


# Maps API error code prefixes/values to exception classes.
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
}


def from_code(code: str, message: str) -> APIError:
    """Return the most specific exception class for the given error code."""
    exc_class = _CODE_MAP.get(code.upper(), APIError)
    return exc_class(code, message)
