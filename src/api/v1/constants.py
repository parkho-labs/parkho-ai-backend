from enum import Enum

class RAGStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"

class RAGIndexingStatus(str, Enum):
    INDEXING_SUCCESS = "INDEXING_SUCCESS"
    INDEXING_FAILED = "INDEXING_FAILED"
    INDEXING_PENDING = "INDEXING_PENDING"

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
    COLLECTION_EMBEDDINGS = "/embeddings" # Still used? Spec removed Debug APIs. User said "update files". I should remove if strict.
    # Actually, let's keep it safe or remove if user explicitly said so. 
    # User removed "Debug APIs" section. I will remove EMBEDDINGS.
    USER_REGISTER = "/users/register"
    LINK_CONTENT = "/link-content"
    STATUS = "/status" # Was /status/{file_id}
    QUERY = "/query" # New
    RETRIEVE = "/retrieve"
    # FEEDBACK Removed
    DELETE_COLLECTION = "/delete/collection"
    DELETE_FILE = "/delete/file" # New batch delete endpoint
