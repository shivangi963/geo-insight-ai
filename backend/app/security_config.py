import os
from typing import List
from dotenv import find_dotenv, load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv(find_dotenv())


class CORSSettings:

    DEVELOPMENT_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:8501",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8501",
        "http://127.0.0.1:8000",
    ]
    
    PRODUCTION_ORIGINS = [
        "https://yourdomain.com",
        "https://app.yourdomain.com",
        "https://api.yourdomain.com",
    ]
    
    STAGING_ORIGINS = [
        "https://staging.yourdomain.com",
        "https://staging-app.yourdomain.com",
    ]
    
    @staticmethod
    def get_cors_config(environment: str = "development") -> dict:
        
        if environment == "production":
            origins = CORSSettings.PRODUCTION_ORIGINS
            allow_credentials = True
            allow_methods = ["GET", "POST", "PUT", "DELETE"]
            allow_headers = ["*"]
        elif environment == "staging":
            origins = CORSSettings.STAGING_ORIGINS
            allow_credentials = True
            allow_methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
            allow_headers = ["*"]
        else:  
            origins = CORSSettings.DEVELOPMENT_ORIGINS
            allow_credentials = True
            allow_methods = ["*"]
            allow_headers = ["*"]
        
        return {
            "allow_origins": origins,
            "allow_credentials": allow_credentials,
            "allow_methods": allow_methods,
            "allow_headers": allow_headers,
            "max_age": 600, 
        }


class RateLimitSettings:
    
    DEFAULT_RATE_LIMIT = "60/minute"

    RATE_LIMITS = {

        "/auth/login": "5/minute",
        "/auth/register": "5/minute",
        
        "/api/neighborhood/analyze": "10/minute",
        "/api/image/analyze": "20/minute",
        "/api/vector-search": "30/minute",
 
        "/api/properties": "60/minute",
        "/api/properties/{id}": "60/minute",

        "/api/download": "20/minute",
    }


class RequestValidationSettings:

    MAX_REQUEST_SIZE = 10 * 1024 * 1024 
    
   
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024  

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

