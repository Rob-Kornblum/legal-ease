from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# ✅ New OpenAI client instance (replaces old openai.api_key approach)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 👇 Define a request body schema
class SimplifyRequest(BaseModel):
    text: str

@app.post("/simplify")
async def simplify_text(request: SimplifyRequest):
    legal_text = request.text

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful legal assistant who rewrites complex legal language into plain English."},
                {"role": "user", "content": legal_text}
            ]
        )
        return {"result": response.choices[0].message.content}
    except Exception as e:
        print("❌ OpenAI Error:", str(e))
        return {"error": str(e)}, 500