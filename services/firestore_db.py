import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from typing import Optional, List, Dict
import os
import json

# Initialize Firebase Admin SDK
def initialize_firestore():
    """Initialize Firestore connection"""
    try:
        # Check if already initialized
        firebase_admin.get_app()
    except ValueError:
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        # Initialize with credentials
        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        
        if cred_path and os.path.exists(cred_path):
            # Use service account file
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            print(f"✅ Initialized Firestore with credentials from: {cred_path}")
        else:
            # Use credentials from environment variable (for deployment)
            cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
            if cred_json:
                cred_dict = json.loads(cred_json)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                print("✅ Initialized Firestore with credentials from environment variable")
            else:
                raise ValueError(
                    "Firebase credentials not found. Please set FIREBASE_CREDENTIALS_PATH "
                    "in .env or FIREBASE_CREDENTIALS_JSON environment variable."
                )
    
    return firestore.client()

# Get Firestore client
db = initialize_firestore()

# Collections
USERS_COLLECTION = "users"
READ_ARTICLES_COLLECTION = "read_articles"

class FirestoreUser:
    """User operations with Firestore"""
    
    @staticmethod
    def create(email: str, hashed_password: str, age: int, goals: str, 
               interests: List[str], k: int = 3) -> Dict:
        """Create a new user"""
        user_data = {
            "email": email,
            "hashed_password": hashed_password,
            "age": age,
            "goals": goals,
            "interests": interests,
            "k": k,
            "created_at": datetime.utcnow(),
            "last_login": datetime.utcnow()
        }
        
        doc_ref = db.collection(USERS_COLLECTION).document()
        doc_ref.set(user_data)
        
        user_data["id"] = doc_ref.id
        return user_data
    
    @staticmethod
    def get_by_email(email: str) -> Optional[Dict]:
        """Get user by email"""
        users_ref = db.collection(USERS_COLLECTION)
        query = users_ref.where("email", "==", email).limit(1)
        docs = query.stream()
        
        for doc in docs:
            user_data = doc.to_dict()
            user_data["id"] = doc.id
            return user_data
        
        return None
    
    @staticmethod
    def get_by_id(user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        doc_ref = db.collection(USERS_COLLECTION).document(user_id)
        doc = doc_ref.get()
        
        if doc.exists:
            user_data = doc.to_dict()
            user_data["id"] = doc.id
            return user_data
        
        return None
    
    @staticmethod
    def update(user_id: str, updates: Dict) -> Dict:
        """Update user profile"""
        doc_ref = db.collection(USERS_COLLECTION).document(user_id)
        doc_ref.update(updates)
        
        return FirestoreUser.get_by_id(user_id)
    
    @staticmethod
    def update_last_login(user_id: str):
        """Update last login timestamp"""
        doc_ref = db.collection(USERS_COLLECTION).document(user_id)
        doc_ref.update({"last_login": datetime.utcnow()})

class FirestoreReadArticle:
    """Read articles operations with Firestore"""
    
    @staticmethod
    def mark_read(user_id: str, article_url: str):
        """Mark an article as read"""
        read_data = {
            "user_id": user_id,
            "article_url": article_url,
            "read_at": datetime.utcnow()
        }
        
        # Check if already exists
        existing = FirestoreReadArticle.get_read_article(user_id, article_url)
        if not existing:
            db.collection(READ_ARTICLES_COLLECTION).add(read_data)
    
    @staticmethod
    def get_read_article(user_id: str, article_url: str) -> Optional[Dict]:
        """Check if article is already read"""
        articles_ref = db.collection(READ_ARTICLES_COLLECTION)
        query = articles_ref.where("user_id", "==", user_id).where("article_url", "==", article_url).limit(1)
        docs = query.stream()
        
        for doc in docs:
            return doc.to_dict()
        
        return None
    
    @staticmethod
    def get_user_read_articles(user_id: str) -> List[str]:
        """Get all read article URLs for a user"""
        articles_ref = db.collection(READ_ARTICLES_COLLECTION)
        query = articles_ref.where("user_id", "==", user_id)
        docs = query.stream()
        
        return [doc.to_dict()["article_url"] for doc in docs]
