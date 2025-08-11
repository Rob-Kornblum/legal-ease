import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app, check_rate_limit, request_timestamps
import time

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
    assert data["category"] == "Non-Legal"

def test_simplify_malformed_json(monkeypatch, caplog):
    class FakeFunction:
        arguments = "not a json"
    
    class FakeToolCall:
        type = "function"
        function = FakeFunction()

    class FakeMessage:
        tool_calls = [FakeToolCall()]

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
            assert data["category"] in {"Other Legal", "Non-Legal"}
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
    """Test input validation for empty text - should now return 422"""
    payload = {"text": ""}
    response = client.post("/simplify", json=payload)
    assert response.status_code == 422

def test_simplify_missing_text_field():
    response = client.post("/simplify", json={})
    assert response.status_code == 422

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

def test_rate_limit_function():
    """Test the rate limiting function directly"""
    
    request_timestamps.clear()
    
    client_id = "test_client"
  
    assert check_rate_limit(client_id, max_requests=2, window_minutes=1) == True
    
    assert check_rate_limit(client_id, max_requests=2, window_minutes=1) == True
    
    assert check_rate_limit(client_id, max_requests=2, window_minutes=1) == False
    
    request_timestamps.clear()

def test_rate_limit_window_expiry():
    """Test that rate limit resets after time window"""
    request_timestamps.clear()
    
    client_id = "test_client_2"

    with patch('main.time.time') as mock_time:
        
        mock_time.return_value = 0
        
        assert check_rate_limit(client_id, max_requests=2, window_minutes=1) == True
        assert check_rate_limit(client_id, max_requests=2, window_minutes=1) == True
        assert check_rate_limit(client_id, max_requests=2, window_minutes=1) == False
       
        mock_time.return_value = 61

        assert check_rate_limit(client_id, max_requests=2, window_minutes=1) == True
    
    request_timestamps.clear()

def test_rate_limit_multiple_clients():
    """Test that rate limiting is per-client"""
    request_timestamps.clear()
    
    client1 = "client_1"
    client2 = "client_2"

    assert check_rate_limit(client1, max_requests=1, window_minutes=1) == True
    assert check_rate_limit(client2, max_requests=1, window_minutes=1) == True

    assert check_rate_limit(client1, max_requests=1, window_minutes=1) == False
    assert check_rate_limit(client2, max_requests=1, window_minutes=1) == False
    
    request_timestamps.clear()

def test_simplify_rate_limiting():
    """Test rate limiting on the /simplify endpoint"""
    request_timestamps.clear()

    with patch('main.check_rate_limit', return_value=False):
        payload = {"text": "The party of the first part shall indemnify the party of the second part."}
        response = client.post("/simplify", json=payload)
        assert response.status_code == 429
        assert "Too many requests" in response.json()["detail"]
    
    request_timestamps.clear()

def test_simplify_rate_limiting_allows_when_under_limit():
    """Test that requests are allowed when under rate limit"""
    request_timestamps.clear()

    with patch('main.check_rate_limit', return_value=True):

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        
        # Mock the new tool_calls format
        mock_tool_call = MagicMock()
        mock_tool_call.type = "function"
        mock_tool_call.function = MagicMock()
        mock_tool_call.function.arguments = '{"category": "Contract", "plain_english": "Test translation"}'
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        
        with patch('main.client.chat.completions.create', return_value=mock_response):
            payload = {"text": "The party of the first part shall indemnify the party of the second part."}
            response = client.post("/simplify", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert "response" in data
            assert "category" in data
    
    request_timestamps.clear()

def test_metrics_endpoint():
    """Test the /metrics endpoint"""
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()

    assert "total_requests_in_window" in data
    assert "active_clients" in data
    assert "server_status" in data

    assert isinstance(data["total_requests_in_window"], int)
    assert isinstance(data["active_clients"], int)
    assert data["server_status"] == "healthy"

def test_metrics_with_request_data():
    """Test metrics endpoint with some request data"""
    request_timestamps.clear()

    request_timestamps["client1"] = [time.time(), time.time() - 30]
    request_timestamps["client2"] = [time.time() - 10]
    request_timestamps["client3"] = []
    
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()

    assert data["total_requests_in_window"] == 3
    
    assert data["active_clients"] == 2
    assert data["server_status"] == "healthy"
    
    request_timestamps.clear()

def test_metrics_endpoint_wrong_method():
    """Test that metrics endpoint only accepts GET"""
    response = client.post("/metrics")
    assert response.status_code == 405

def test_simplify_input_validation_empty_text():
    """Test input validation for empty text"""
    payload = {"text": ""}
    response = client.post("/simplify", json=payload)
    assert response.status_code == 422

def test_simplify_input_validation_whitespace_only():
    """Test input validation for whitespace-only text"""
    payload = {"text": "   \n\t   "}
    response = client.post("/simplify", json=payload)
    assert response.status_code == 422

def test_simplify_input_validation_too_short():
    """Test input validation for text that's too short"""
    payload = {"text": "Hi there"}
    response = client.post("/simplify", json=payload)
    assert response.status_code == 422

def test_simplify_input_validation_too_long():
    """Test input validation for text that's too long"""
    payload = {"text": "A" * 2001}
    response = client.post("/simplify", json=payload)
    assert response.status_code == 422

def test_simplify_input_validation_valid_input():
    """Test that valid input passes validation"""
    with patch('main.check_rate_limit', return_value=True):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        
        # Mock the new tool_calls format
        mock_tool_call = MagicMock()
        mock_tool_call.type = "function"
        mock_tool_call.function = MagicMock()
        mock_tool_call.function.arguments = '{"category": "Contract", "plain_english": "Valid test translation"}'
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        
        with patch('main.client.chat.completions.create', return_value=mock_response):
            payload = {"text": "This is a valid legal text that is long enough to pass validation."}
            response = client.post("/simplify", json=payload)
            assert response.status_code == 200

def test_simplify_response_includes_new_fields():
    """Test that response includes confidence and word_count fields"""
    with patch('main.check_rate_limit', return_value=True):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        
        # Mock the new tool_calls format
        mock_tool_call = MagicMock()
        mock_tool_call.type = "function"
        mock_tool_call.function = MagicMock()
        mock_tool_call.function.arguments = '{"category": "Contract", "plain_english": "Test translation"}'
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        
        with patch('main.client.chat.completions.create', return_value=mock_response):
            payload = {"text": "The party of the first part shall indemnify and hold harmless the party of the second part."}
            response = client.post("/simplify", json=payload)
            assert response.status_code == 200
            data = response.json()
            
            assert "confidence" in data
            assert "word_count" in data
            
            assert data["confidence"] == "high"
            assert data["word_count"] == len(payload["text"].split())

def test_simplify_confidence_medium_for_short_text():
    """Test that confidence is 'medium' for shorter text"""
    with patch('main.check_rate_limit', return_value=True):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        
        mock_tool_call = MagicMock()
        mock_tool_call.type = "function"
        mock_tool_call.function = MagicMock()
        mock_tool_call.function.arguments = '{"category": "Contract", "plain_english": "Test translation"}'
        mock_response.choices[0].message.tool_calls = [mock_tool_call]

        with patch('main.client.chat.completions.create', return_value=mock_response):

            payload = {"text": "This legal contract has exactly ten words in total here."}
            response = client.post("/simplify", json=payload)
            assert response.status_code == 200
            data = response.json()
            
            assert data["confidence"] == "medium"
            assert data["word_count"] == 10