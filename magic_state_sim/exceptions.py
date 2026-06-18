"""Custom exceptions for magic_state_sim."""

class MagicStateSimError(Exception):
    """Base exception for simulator errors."""

class ValidationError(MagicStateSimError, ValueError):
    """Raised when simulator input validation fails."""

class InsufficientTokensError(MagicStateSimError):
    """Raised when a component cannot supply enough tokens."""

class MemoryFullError(MagicStateSimError):
    """Raised when finite memory capacity would be exceeded."""
