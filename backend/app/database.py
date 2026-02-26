import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from dotenv import find_dotenv, load_dotenv
import asyncio
import logging

load_dotenv(find_dotenv())
logger = logging.getLogger(__name__)

class Database:
    client = None
    db = None
    _is_connected = False
    _lock = asyncio.Lock()
    
    @classmethod
    async def connect(cls):
        async with cls._lock:
            if cls.client is not None and cls._is_connected:
                return cls.db
            
            MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
            DATABASE_NAME = os.getenv("DATABASE_NAME", "geoinsight_ai")
            
            logger.info(f"Connecting to MongoDB: {MONGODB_URL}")
            logger.info(f"Database: {DATABASE_NAME}")
            
            try:
                cls.client = AsyncIOMotorClient(
                    MONGODB_URL,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                    socketTimeoutMS=5000,
                    maxPoolSize=50
                )
                cls.db = cls.client[DATABASE_NAME]
                
                await cls.client.admin.command('ping')
                cls._is_connected = True
                
                logger.info("MongoDB connected successfully")
                
                collections = await cls.db.list_collection_names()
                logger.info(f"Available collections: {collections}")
                
                return cls.db
                
            except Exception as e:
                cls._is_connected = False
                logger.error(f" MongoDB connection failed: {e}")
                raise ConnectionError(f"Cannot connect to MongoDB: {e}")
    
    @classmethod
    async def is_connected(cls) -> bool:
        if not cls._is_connected or cls.client is None:
            return False
        try:
            await cls.client.admin.command("ping")
            return True
        except Exception:
            cls._is_connected = False
            return False
    
    @classmethod
    async def get_database(cls):
        if not cls._is_connected:
            await cls.connect()
        return cls.db
    
    @classmethod
    async def close(cls):
        if cls.client:
            cls.client.close()
            cls.client = None
            cls.db = None
            cls._is_connected = False
            logger.info(" MongoDB disconnected")


async def get_database():
    return await Database.get_database()

def get_sync_database():
    MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "geoinsight_ai")
    
    logger.info(f"Creating sync connection: {MONGODB_URL}")
    
    try:
        
        client = MongoClient(
            MONGODB_URL,
            serverSelectionTimeoutMS=5000
        )
        client.admin.command('ping')
        db = client[DATABASE_NAME]
        logger.info(" Sync MongoDB connected")
        return client, db
    except Exception as e:
        logger.error(f" Sync connection failed: {e}")
        raise

async def initialize_database():
    try:
        db = await get_database()
        collections = await db.list_collection_names()
     
        required_collections = [
            "properties",
            "neighborhood_analyses",
            "satellite_analyses"
        ]
        
        for coll_name in required_collections:
            if coll_name not in collections:
                await db.create_collection(coll_name)
                logger.info(f" Created collection: {coll_name}")
        
        await db.properties.create_index("address")
        await db.properties.create_index("city")
        await db.properties.create_index([("latitude", 1), ("longitude", 1)])
        
        await db.neighborhood_analyses.create_index("created_at")
        await db.neighborhood_analyses.create_index("status")
        
        logger.info(" Database initialized")
        
    except Exception as e:
        logger.error(f" Database initialization failed: {e}")