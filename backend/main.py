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
import re
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

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5")
logger.info(f"Using OpenAI model: {MODEL_NAME}")

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

LEGAL_KEYWORDS = {
    "hereby", "whereas", "hereto", "thereof", "therein", "witnesseth", "indemnify",
    "party", "parties", "agreement", "contract", "jurisdiction", "liability", "estate",
    "testament", "bequeath", "assigns", "successors", "covenant", "breach", "damages",
    "negligence", "statute", "clause", "confidentiality", "arbitration", "merger", "legalese"
}

def is_potentially_legal(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in LEGAL_KEYWORDS)

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
    words = legal_text.split()
    if not is_potentially_legal(legal_text) and len(words) < 8:
        confidence = "medium" if len(words) <= 12 else "high"
        return {
            "response": legal_text.strip(),
            "category": "Other",
            "confidence": confidence,
            "word_count": len(words),
            "parse_confidence": "heuristic"
        }
    system_prompt = prompt_env.get_template("legal_assistant_v4.txt").render()

    logger.info(f"Received request: {legal_text!r}")

    try:
        completion_kwargs = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": legal_text}
            ],
            "functions": functions,
            "function_call": {"name": "classify_legal_area"},
        }
        
        if not MODEL_NAME.startswith("gpt-5"):
            completion_kwargs["temperature"] = 0.1
        if MODEL_NAME.startswith("gpt-5"):
            completion_kwargs["max_completion_tokens"] = 500
        else:
            completion_kwargs["max_tokens"] = 500

        response = client.chat.completions.create(**completion_kwargs)
        choice = response.choices[0].message

        args_str = None
        if hasattr(choice, "function_call") and getattr(choice.function_call, "arguments", None):
            args_str = choice.function_call.arguments
        elif hasattr(choice, "tool_calls") and choice.tool_calls:
            for tc in choice.tool_calls:
                try:
                    if getattr(tc, "type", "") == "function":
                        fn = getattr(tc, "function", None)
                        if fn and getattr(fn, "arguments", None):
                            args_str = fn.arguments
                            break
                except Exception:
                    continue

        parsed = {}
        parse_confidence = "low"
        if args_str:
            try:
                parsed = json.loads(args_str)
                parse_confidence = "high"
            except Exception as parse_err:
                logger.error(f"Parse Error decoding function arguments: {parse_err}")
                # Keep category empty; put raw args in plain_english and also mark for direct response usage
                parsed = {"category": "", "plain_english": args_str, "__raw_args": True}
                parse_confidence = "low"
        else:
            # Fallback: attempt to extract JSON from raw content
            content = getattr(choice, "content", "") or ""
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                try:
                    candidate = json.loads(json_match.group(0))
                    if isinstance(candidate, dict):
                        parsed = candidate
                        parse_confidence = "medium"
                except Exception:
                    pass
            if not parsed:
                # Last resort: treat content as plain English explanation
                parsed = {
                    "category": "",
                    "plain_english": content.strip()
                }

        if not parsed.get("category"):
            parsed["category"] = "Other" if not is_potentially_legal(legal_text) else ""
        confidence = "high" if len(legal_text.split()) > 10 else "medium"
        # If this was a raw malformed arguments fallback, ensure response returns exactly the raw string
        response_text = parsed.get("plain_english", "")
        if parsed.get("__raw_args"):
            response_text = parsed.get("plain_english", "")
        return {
            "response": response_text,
            "category": parsed.get("category", ""),
            "confidence": confidence,
            "word_count": len(legal_text.split()),
            "parse_confidence": parse_confidence
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