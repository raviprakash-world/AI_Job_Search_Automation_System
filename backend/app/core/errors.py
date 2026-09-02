class AppError(Exception):
    """Base class for domain errors mapped to a consistent JSON error envelope."""

    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationFailedError(AppError):
    status_code = 422
    code = "validation_failed"


class ExtractionValidationError(AppError):
    """Raised when AI extraction output fails schema validation after retry."""

    status_code = 422
    code = "extraction_validation_failed"


class AuthError(AppError):
    status_code = 401
    code = "auth_error"


class UnsupportedFileTypeError(AppError):
    status_code = 415
    code = "unsupported_file_type"


class ProviderError(AppError):
    """Raised when a job-source provider's API is unreachable or returns unexpected data."""

    status_code = 502
    code = "provider_error"
