"""Error types for the DOFBOT driver package."""


class DofbotError(Exception):
    """Base error for all DOFBOT driver failures."""


class DofbotValidationError(DofbotError):
    """Raised when caller input is outside configured constraints."""


class DofbotConnectionError(DofbotError):
    """Raised when transport communication repeatedly fails."""
