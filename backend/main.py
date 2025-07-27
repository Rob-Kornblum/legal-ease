from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
from pydantic import BaseModel
from openai import OpenAI
from jinja2 import Environment, FileSystemLoader
import os
from dotenv import load_dotenv
import logging
import json

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

class SimplifyRequest(BaseModel):
    text: str

@app.post("/simplify")
async def simplify_text(request: SimplifyRequest):
    legal_text = request.text
    system_prompt = prompt_env.get_template("legal_assistant_v4.txt").render()

    logger.info(f"Received request: {legal_text!r}")

    try:
        response = client.chat.completions.create(
            model="gpt-4-0613",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": legal_text}
            ],
            functions=functions,
            function_call={"name": "classify_legal_area"}
        )
        args = response.choices[0].message.function_call.arguments
        try:
            parsed = json.loads(args)
            return {
                "response": parsed.get("plain_english", ""),
                "category": parsed.get("category", "")
            }
        except Exception as parse_err:
            logger.error(f"Parse Error: {str(parse_err)}")
            return {
                "response": args,
                "category": ""
            }
    except Exception as e:
        logger.error(f"OpenAI Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint

@app.get("/health")
def health():
    return {"status": "ok"}