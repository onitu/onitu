class _HandlerException(Exception):
    pass


class DriverError(_HandlerException):
    status_code = 1


class ServiceError(_HandlerException):
    status_code = 2
