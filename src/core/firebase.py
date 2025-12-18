import os
import asyncio
from typing import Optional, Dict, Any
import firebase_admin
from firebase_admin import auth, credentials
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models.user import User
# RAG service import removed - register_user not part of documented API

settings = get_settings()

_firebase_app = None

def initialize_firebase():
    global _firebase_app
    if _firebase_app is None:
        try:
            # Check for local file first (Development/Faster)
            if os.path.exists(settings.firebase_service_account_path):
                cred = credentials.Certificate(settings.firebase_service_account_path)
            else:
                # Try Secret Manager (Production fallback)
                secret_name = os.getenv('FIREBASE_SECRET_NAME', 'firebase-service-account')
                try:
                    from google.cloud import secretmanager
                    client = secretmanager.SecretManagerServiceClient()
                    name = f"projects/{settings.firebase_project_id}/secrets/{secret_name}/versions/latest"
                    response = client.access_secret_version(request={"name": name})
                    import json
                    service_account_info = json.loads(response.payload.data.decode("UTF-8"))
                    cred = credentials.Certificate(service_account_info)
                except Exception as e:
                    print(f"Secret Manager initialization failed: {e}")
                    raise e

            _firebase_app = firebase_admin.initialize_app(cred, {
                'projectId': settings.firebase_project_id
            })
        except Exception as e:
            print(f"Firebase initialization failed: {e}")
            return None
    return _firebase_app

def verify_firebase_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        app = initialize_firebase()
        if not app:
             print("Firebase app not initialized")
             return None
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        print(f"Token verification failed: {e}")
        return None

async def get_or_create_user(db: Session, firebase_uid: str, email: str, full_name: str, date_of_birth: str = None) -> User:
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if user:
        return user

    try:
        user = User(
            user_id=firebase_uid,
            firebase_uid=firebase_uid,
            email=email,
            full_name=full_name,
            date_of_birth=date_of_birth
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # RAG user registration removed - not part of documented RAG Engine API
        # Users are identified by x-user-id header in RAG requests

        return user
    except Exception as e:
        db.rollback()
        raise Exception(f"Failed to create user: {str(e)}")

def get_or_create_user_sync(db: Session, firebase_uid: str, email: str, full_name: str, date_of_birth: str = None) -> User:
    return asyncio.run(get_or_create_user(db, firebase_uid, email, full_name, date_of_birth))