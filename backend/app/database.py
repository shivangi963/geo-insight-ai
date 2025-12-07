import pymongo
import os
from dotenv import load_dotenv

load_dotenv()

class Database:
    client = None
    db = None

    @classmethod
    def connect(cls):
        """Connect to MongoDB"""
        if cls.client is None:
            mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
            database_name = os.getenv("DATABASE_NAME", "geoinsight_ai")
            
            cls.client = pymongo.MongoClient(mongodb_url)
            cls.db = cls.client[database_name]
            print("✅ Connected to MongoDB!")
        return cls.db

    @classmethod
    def get_collection(cls, collection_name: str):
        """Get a collection from database"""
        if cls.db is None:
            cls.connect()
        return cls.db[collection_name]

    @classmethod
    def close(cls):
        """Close database connection"""
        if cls.client:
            cls.client.close()
            print("❌ Disconnected from MongoDB")