import os
from dotenv import load_dotenv, find_dotenv


load_dotenv(find_dotenv())
class Settings:
    APP_NAME: str = "GeoInsight AI"
    APP_VERSION: str = "4.3.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "geoinsight_ai")

settings = Settings()