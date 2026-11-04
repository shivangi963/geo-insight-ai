"""GET /api/properties against an in-memory database.

Regression: the router passed `city=` to crud.get_all_properties, which did not accept
it, so every request returned HTTP 500.
"""

import inspect

from backend.app.crud import PropertyCRUD

from .conftest import property_doc, seed


def test_router_and_crud_signatures_agree():
    assert "city" in inspect.signature(PropertyCRUD.get_all_properties).parameters


def test_list_properties_returns_200(client, mock_db):
    seed(mock_db, "properties", [property_doc(), property_doc(price=7_000_000)])
    response = client.get("/api/properties")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_city_filter_is_applied_before_pagination(client, mock_db):
    mumbai = [property_doc("Mumbai", price=1_000_000 + i) for i in range(5)]
    pune = [property_doc("Pune", price=2_000_000 + i) for i in range(5)]
    seed(mock_db, "properties", mumbai + pune)  # Mumbai documents come first

    response = client.get("/api/properties", params={"city": "Pune", "limit": 3})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    assert {p["city"] for p in body} == {"Pune"}


def test_city_filter_ignores_case(client, mock_db):
    seed(mock_db, "properties", [property_doc("Mumbai"), property_doc("Pune")])
    response = client.get("/api/properties", params={"city": "mumbai"})
    assert [p["city"] for p in response.json()] == ["Mumbai"]


def test_documents_written_by_the_loader_are_returned(client, mock_db):
    """load_kaggle_data.py does not write zip_code; such documents must still validate."""
    seed(mock_db, "properties", [property_doc(with_zip=False)])
    response = client.get("/api/properties")
    assert response.status_code == 200
    assert len(response.json()) == 1
