from enum import Enum

class RAGStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"

class RAGIndexingStatus(str, Enum):
    INDEXING_SUCCESS = "INDEXING_SUCCESS"
    INDEXING_FAILED = "INDEXING_FAILED"
    INDEXING_PENDING = "INDEXING_PENDING"
    AGENT_PROCESSING = "AGENT_PROCESSING"

class RAGContentType(str, Enum):
    FILE = "file"
    TEXT = "text"
    URL = "url"

class RAGResponseKey:
    STATUS = "status"
    BODY = "body"
    MESSAGE = "message"
    FILE_ID = "file_id"
    FILENAME = "filename"
    COLLECTIONS = "collections"
    FILES = "files"
    STATUS_CODE = "status_code"
    INDEXING_STATUS = "indexing_status"


class RAGEndpoint:
    FILES = "/files"
    FILE_BY_ID = "/files/{file_id}"
    COLLECTION = "/collection"
    COLLECTIONS = "/collections"
    COLLECTION_LINK_CONTENT = "/{collection_name}/link-content"
    COLLECTION_UNLINK_CONTENT = "/{collection_name}/unlink-content"
    COLLECTION_FILES = "/{collection_name}/files"
    COLLECTION_QUERY = "/{collection_name}/query"
    COLLECTION_QUERY = "/{collection_name}/query"
    # COLLECTION_EMBEDDINGS removed per spec
    USER_REGISTER = "/users/register"
    LINK_CONTENT = "/link-content"
    COLLECTION_STATUS = "/collection/status" # New Doc
    STATUS = "/collection/status" # Alias for backward compat if needed, or update usage
    QUERY = "/query"
    RETRIEVE = "/retrieve"
    # FEEDBACK Removed
    DELETE_COLLECTION = "/delete/collection"
    DELETE_FILE = "/delete/file"


class StorageConfig:
    GCS_DOMAIN = "storage.googleapis.com"
    UPLOADS_DIR = "uploaded_files"
    SYSTEM_UPLOADS_PREFIX = "uploads/system"


class ErrorConstants:
    UNDEFINED_ID = "undefined"
    ANONYMOUS_USER = "anonymous-user"
