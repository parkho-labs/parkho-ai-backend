import os
import asyncio
from typing import Optional, Dict, Any
import firebase_admin
from firebase_admin import auth, credentials
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models.user import User
from ..services.rag_integration_service import get_rag_service

settings = get_settings()

_firebase_app = None

def initialize_firebase():
    global _firebase_app
    if _firebase_app is None:
        try:
            # Try Secret Manager (production) or local file (development)
            secret_name = os.getenv('FIREBASE_SECRET_NAME', 'firebase-service-account')

            try:
                from google.cloud import secretmanager
                client = secretmanager.SecretManagerServiceClient()
                name = f"projects/{settings.firebase_project_id}/secrets/{secret_name}/versions/latest"
                response = client.access_secret_version(request={"name": name})
                import json
                service_account_info = json.loads(response.payload.data.decode("UTF-8"))
                cred = credentials.Certificate(service_account_info)
            except:
                # Fallback to local file
                cred = credentials.Certificate(settings.firebase_service_account_path)

            _firebase_app = firebase_admin.initialize_app(cred, {
                'projectId': settings.firebase_project_id
            })
        except Exception as e:
            print(f"Firebase initialization failed: {e}")
            return None
    return _firebase_app

def verify_firebase_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        initialize_firebase()
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception:
        return None

async def get_or_create_user(db: Session, firebase_uid: str, email: str, full_name: str, date_of_birth: str = None) -> User:
    """
    Get existing user or create a new one with RAG engine registration.

    This function ensures atomic operation - either both local DB and RAG engine
    get the user, or neither does (with rollback on failure).

    Args:
        db: Database session
        firebase_uid: Firebase UID (used as RAG engine user_id)
        email: User email
        full_name: User's full name
        date_of_birth: Optional date of birth

    Returns:
        User: The created or existing user

    Raises:
        Exception: If RAG engine registration fails during user creation
    """
    # Check if user already exists
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if user:
        # User already exists, no need to register with RAG engine again
        return user

    # User doesn't exist, create new user with RAG registration
    rag_service = get_rag_service()

    try:
        # Start database transaction
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            full_name=full_name,
            date_of_birth=date_of_birth
        )
        db.add(user)
        db.flush()  # Flush to get user.user_id but don't commit yet

        # Register user with RAG engine using Firebase UID
        await rag_service.register_user(firebase_uid, email, full_name)

        # If RAG registration succeeds, commit the database transaction
        db.commit()
        db.refresh(user)

        return user

    except Exception as e:
        # If anything fails, rollback the database transaction
        db.rollback()
        raise Exception(f"Failed to create user: {str(e)}")

def get_or_create_user_sync(db: Session, firebase_uid: str, email: str, full_name: str, date_of_birth: str = None) -> User:
    """
    Synchronous wrapper for get_or_create_user for backward compatibility.
    """
    return asyncio.run(get_or_create_user(db, firebase_uid, email, full_name, date_of_birth))