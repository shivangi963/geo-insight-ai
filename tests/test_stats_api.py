"""GET /api/stats, which the dashboard calls. It must report exact counts."""

from backend.app.crud import NEIGHBORHOOD_ANALYSIS_COLLECTION

from .conftest import property_doc, seed


def test_stats_endpoint_exists_and_counts_exactly(client, mock_db):
    docs = [property_doc("Mumbai", price=1_000_000) for _ in range(1_200)]
    docs += [property_doc("Pune", price=3_000_000) for _ in range(300)]
    seed(mock_db, "properties", docs)
    seed(mock_db, NEIGHBORHOOD_ANALYSIS_COLLECTION, [{"status": "completed"} for _ in range(3)])

    response = client.get("/api/stats")

    assert response.status_code == 200
    stats = response.json()
    assert stats["total_properties"] == 1_500  # not capped at 1,000
    assert stats["unique_cities"] == 2
    assert stats["total_analyses"] == 3
    assert stats["average_price"] == (1_200 * 1_000_000 + 300 * 3_000_000) / 1_500


def test_stats_on_an_empty_database(client, mock_db):
    stats = client.get("/api/stats").json()
    assert stats["total_properties"] == 0
    assert stats["average_price"] == 0
