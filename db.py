import os
from dotenv import load_dotenv

load_dotenv()

from pymongo import MongoClient

# MongoDB Configuration
MONGO_URI = os.environ.get('MONGO_URI')

# Connection caching for serverless environments
# Vercel reuses the same process for multiple requests, so we cache the client
_client = None
_db = None

def get_db_connection():
    """
    Get MongoDB database connection.
    Returns the 'inventro' database object.
    Uses connection caching to avoid creating new connections per request.
    """
    global _client, _db
    
    # Return cached connection if available
    if _db is not None:
        try:
            # Quick check if connection is still alive
            _client.admin.command('ping')
            return _db
        except Exception:
            # Connection died, reset and reconnect
            _client = None
            _db = None
    
    uri = MONGO_URI or os.environ.get('MONGO_URI')
    
    if not uri or 'mongodb+srv://<username>' in uri:
        print("WARNING: MONGO_URI is not set or is using the placeholder!")
        return None

    try:
        _client = MongoClient(uri)
        # Verify connection
        _client.admin.command('ping')
        
        # Get database
        _db = _client.get_database('inventro')
        return _db
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        _client = None
        _db = None
        return None

def init_db():
    # MongoDB doesn't need explicit schema initialization
    print("MongoDB does not require schema initialization.")
    pass

if __name__ == '__main__':
    db = get_db_connection()
    if db is not None:
        print("Successfully connected to MongoDB!")
    else:
        print("Failed to connect to MongoDB.")
