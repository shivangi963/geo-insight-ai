"""Shared test setup.

Heavy third-party libraries are replaced with stubs so the suite runs in seconds and
needs no GPU, model downloads or network. MongoDB is replaced by an in-memory
mongomock database. Nothing here talks to Gemini, OpenStreetMap or Supabase.
"""

import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("MONGODB_URL", "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=200")
os.environ.pop("GOOGLE_API_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)

_HEAVY = [
    "folium", "folium.plugins",
    "geopy", "geopy.geocoders", "geopy.distance", "geopy.exc",
    "osmnx", "supabase", "transformers", "torch", "torchvision",
]
for _name in _HEAVY:
    sys.modules.setdefault(_name, MagicMock())

# `google` is a namespace package; give it a stub so `import google.generativeai` works.
_google = sys.modules.setdefault("google", types.ModuleType("google"))
_google.__path__ = getattr(_google, "__path__", [])
_genai = sys.modules.setdefault("google.generativeai", MagicMock())
_google.generativeai = _genai


@pytest.fixture()
def mock_db():
    """An empty in-memory MongoDB wired into the app's Database class."""
    from mongomock_motor import AsyncMongoMockClient

    from backend.app.database import Database

    client = AsyncMongoMockClient()
    Database.client = client
    Database.db = client["test_db"]
    Database._is_connected = True
    yield Database.db
    Database.client = None
    Database.db = None
    Database._is_connected = False


@pytest.fixture()
def client(mock_db):
    """FastAPI test client. Not used as a context manager, so no startup/DB connect runs."""
    from fastapi.testclient import TestClient

    from backend.app.main import app

    return TestClient(app)


def seed(db, collection, docs):
    """Insert documents synchronously (the mock stores data independent of the event loop)."""
    import asyncio

    asyncio.run(db[collection].insert_many(docs))


def property_doc(city="Mumbai", price=9_500_000.0, with_zip=True, **extra):
    """A property document shaped like the ones the loader / API create."""
    doc = {
        "address": f"Test Street, {city}",
        "city": city,
        "state": "Maharashtra",
        "price": price,
        "bedrooms": 2,
        "square_feet": 650,
        "property_type": "Apartment",
    }
    if with_zip:
        doc["zip_code"] = "400001"
    doc.update(extra)
    return doc
