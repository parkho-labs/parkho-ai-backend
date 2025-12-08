class ParkhoError(Exception):
    pass


class ParsingError(ParkhoError):
    pass


class ValidationError(ParkhoError):
    pass


class FileProcessingError(ParsingError):
    pass


class NetworkError(ParsingError):
    pass


class WorkflowError(ParkhoError):
    pass


class JobError(WorkflowError):
    pass


class JobNotFoundError(JobError):
    pass


class DatabaseError(ParkhoError):
    pass


class ExternalServiceError(ParkhoError):
    pass


class TranscriptionError(ExternalServiceError):
    pass


class LLMServiceError(ExternalServiceError):
    pass