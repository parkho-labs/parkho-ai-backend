import os
from typing import Optional, Dict, Any
import firebase_admin
from firebase_admin import auth, credentials
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models.user import User

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

def get_or_create_user(db: Session, firebase_uid: str, email: str, full_name: str, date_of_birth: str = None) -> User:
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            full_name=full_name,
            date_of_birth=date_of_birth
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user