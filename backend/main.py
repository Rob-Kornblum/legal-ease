from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# New OpenAI client instance
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

class SimplifyRequest(BaseModel):
    text: str

# Endpoint to simplify legal text
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

# Health check endpoint

@app.get("/health")
def health():
    return {"status": "ok"}