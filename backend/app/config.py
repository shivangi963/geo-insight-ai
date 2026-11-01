import os
from typing import List
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


class Settings:
    # Application Settings
    APP_NAME: str = "GeoInsight AI"
    APP_VERSION: str = "4.3.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Database Settings
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "geoinsight_ai")

    # CORS Configuration
    # Replaced placeholder 'yourdomain.com' with configurable origins and deployed frontend URLs
    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:3000,"
            "http://localhost:8501,"
            "http://localhost:8000,"
            "http://127.0.0.1:3000,"
            "https://geoinsight-ai.web.app,"
            "https://geoinsight-frontend.run.app"
        ).split(",")
        if origin.strip()
    ]


class RequestValidationSettings:
    MAX_REQUEST_SIZE: int = 10 * 1024 * 1024   # 10 MB
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024    # 50 MB

    ALLOWED_FILE_EXTENSIONS = {
        "images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"},
        "documents": {".pdf", ".txt", ".csv", ".xlsx", ".json"},
        "data": {".csv", ".json", ".geojson", ".shp"},
    }

    VALIDATION_RULES = {
        "min_query_length": 1,
        "max_query_length": 500,
        "min_password_length": 8,
        "max_batch_size": 1000,
        "min_lat": -90,
        "max_lat": 90,
        "min_lon": -180,
        "max_lon": 180,
    }


settings = Settings()