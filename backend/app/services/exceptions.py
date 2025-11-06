"""
Service Layer Exceptions

Custom exceptions for service layer error handling.
"""


class ServiceError(Exception):
    """Base exception for service layer errors"""

    pass


class NotFoundError(ServiceError):
    """Resource not found in database"""

    def __init__(self, resource_type: str, identifier: str):
        self.resource_type = resource_type
        self.identifier = identifier
        super().__init__(f"{resource_type} not found: {identifier}")


class DuplicateError(ServiceError):
    """Resource already exists in database"""

    def __init__(self, resource_type: str, field: str, value: str):
        self.resource_type = resource_type
        self.field = field
        self.value = value
        super().__init__(f"{resource_type} with {field}='{value}' already exists")


class ValidationError(ServiceError):
    """Invalid data provided to service"""

    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(f"Validation error on '{field}': {message}")


class ProcessingError(ServiceError):
    """Error during data processing"""

    pass


class ExternalServiceError(ServiceError):
    """Error communicating with external service (API, RSS feed, etc.)"""

    def __init__(self, service_name: str, message: str):
        self.service_name = service_name
        super().__init__(f"External service error ({service_name}): {message}")
