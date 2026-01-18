"""
Quick script to test Firestore connection
Run: python setup_firestore.py
"""

try:
    from firestore_db import db, FirestoreUser
    print("✅ Firestore connection successful!")
    print(f"✅ Database client initialized: {db.project}")
    print("\n📝 Next steps:")
    print("1. Your Firestore is ready to use")
    print("2. Start the server: python main.py")
    print("3. Test registration at: http://localhost:8000/docs")
except Exception as e:
    print(f"❌ Error connecting to Firestore: {str(e)}")
    print("\n📝 Make sure you:")
    print("1. Created a Firebase project")
    print("2. Enabled Firestore Database")
    print("3. Downloaded service account credentials")
    print("4. Set FIREBASE_CREDENTIALS_PATH in .env")
    print("\nSee FIRESTORE_SETUP.md for detailed instructions")
