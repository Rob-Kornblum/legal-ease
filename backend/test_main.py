import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_health_wrong_method():
    response = client.post("/health")
    assert response.status_code == 405

def test_simplify_contract():
    payload = {"text": "The party of the first part shall indemnify the party of the second part."}
    response = client.post("/simplify", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "category" in data

def test_simplify_nonlegal():
    payload = {"text": "I love movies."}
    response = client.post("/simplify", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Other"

def test_simplify_malformed_json(monkeypatch, caplog):
    class FakeFunctionCall:
        arguments = "not a json"

    class FakeMessage:
        function_call = FakeFunctionCall()

    class FakeChoices:
        def __init__(self):
            self.message = FakeMessage()
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = type("FakeResponse", (), {"choices": [FakeChoices()]})()

    with patch("main.client", fake_client):
        payload = {"text": "Some legalese"}
        with caplog.at_level("ERROR"):
            response = client.post("/simplify", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["response"] == "not a json"
            assert data["category"] == ""
            assert any("Parse Error" in record.message for record in caplog.records)

def test_simplify_openai_error(monkeypatch, caplog):
    def raise_exception(*args, **kwargs):
        raise Exception("OpenAI API failed")
    with patch("main.client.chat.completions.create", raise_exception):
        payload = {"text": "Some legalese"}
        with caplog.at_level("ERROR"):
            response = client.post("/simplify", json=payload)
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert any("OpenAI Error" in record.message for record in caplog.records)

def test_simplify_empty_input():
    payload = {"text": ""}
    response = client.post("/simplify", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "category" in data

def test_simplify_missing_text_field():
    response = client.post("/simplify", json={})
    assert response.status_code == 422  # Unprocessable Entity (validation error)

def test_simplify_non_string_input():
    payload = {"text": 12345}
    response = client.post("/simplify", json=payload)
    assert response.status_code == 422

def test_cors_headers():
    response = client.options(
        "/simplify",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST"
        }
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers