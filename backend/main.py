from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator
from openai import OpenAI
from jinja2 import Environment, FileSystemLoader
import os
from dotenv import load_dotenv
import logging
import json
import time
from collections import defaultdict

functions = [
    {
        "name": "classify_legal_area",
        "description": "Classifies the legal area and translates legal language into plain English.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "The legal area, e.g., Contract, Real Estate, Personal Injury, Family Law, etc."
                },
                "plain_english": {
                    "type": "string",
                    "description": "The plain English translation of the legal text."
                }
            },
            "required": ["category", "plain_english"]
        }
    }
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

frontend_origin = os.getenv("FRONTEND_ORIGIN")
origins = ["http://localhost:3000"]
if frontend_origin:
    origins.append(frontend_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

prompt_env = Environment(loader=FileSystemLoader("prompts"))

request_timestamps = defaultdict(list)

class SimplifyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, description="Legal text to translate")
    
    @field_validator('text')
    @classmethod
    def validate_text(cls, v):
        if not v.strip():
            raise ValueError('Text cannot be empty or only whitespace')

        if len(v.strip()) < 10:
            raise ValueError('Input too short - please provide substantial legal text')
        return v.strip()

def check_rate_limit(client_ip: str, max_requests: int = 10, window_minutes: int = 1) -> bool:
    """Simple rate limiting: max_requests per window_minutes"""
    now = time.time()
    window_start = now - (window_minutes * 60)
    
    request_timestamps[client_ip] = [
        timestamp for timestamp in request_timestamps[client_ip] 
        if timestamp > window_start
    ]

    if len(request_timestamps[client_ip]) >= max_requests:
        return False
    
    request_timestamps[client_ip].append(now)
    return True

@app.post("/simplify")
async def simplify_text(request: SimplifyRequest):
    request_key = hash(request.text) % 1000
    if not check_rate_limit(str(request_key)):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
    
    legal_text = request.text
    system_prompt = prompt_env.get_template("legal_assistant_v4.txt").render()

    logger.info(f"Received request: {legal_text!r}")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": legal_text}
            ],
            functions=functions,
            function_call={"name": "classify_legal_area"},
            temperature=0.1,
            max_tokens=500
        )
        args = response.choices[0].message.function_call.arguments
        try:
            parsed = json.loads(args)
            confidence = "high" if len(legal_text.split()) > 10 else "medium"
            return {
                "response": parsed.get("plain_english", ""),
                "category": parsed.get("category", ""),
                "confidence": confidence,
                "word_count": len(legal_text.split())
            }
        except Exception as parse_err:
            logger.error(f"Parse Error: {str(parse_err)}")
            return {
                "response": args,
                "category": "",
                "confidence": "low",
                "word_count": len(legal_text.split())
            }
    except Exception as e:
        logger.error(f"OpenAI Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/metrics")
def get_metrics():
    total_requests = sum(len(timestamps) for timestamps in request_timestamps.values())
    active_clients = len([k for k, v in request_timestamps.items() if v])
    return {
        "total_requests_in_window": total_requests,
        "active_clients": active_clients,
        "server_status": "healthy"
    }