"""Domain errors. Each service's server/errors.py maps them to JSON responses
of the form {"error": {"code", "component", "message"}}."""


class DomainError(Exception):
    code = "domain_error"
    status = 400

    def __init__(self, message: str, component: str = ""):
        super().__init__(message)
        self.message = message
        self.component = component


class NotFoundError(DomainError):
    code = "not_found"
    status = 404

    def __init__(self, what: str, key: str, component: str = ""):
        super().__init__(f"{what} not found: {key}", component)


class ConflictError(DomainError):
    code = "conflict"
    status = 409


class InvalidRequestError(DomainError):
    code = "invalid_request"
    status = 422


class ConfigurationError(DomainError):
    """Something in .env / llm.env is missing or wrong; the message says what to change."""
    code = "configuration_error"
    status = 503
