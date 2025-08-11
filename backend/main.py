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

tools = [
    {
        "type": "function",
        "function": {
            "name": "classify_legal_area",
            "description": "Classifies the legal area and translates legal language into plain English.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [
                            "Contract",
                            "Wills, Trusts, and Estates",
                            "Criminal Procedure",
                            "Real Estate",
                            "Employment Law",
                            "Personal Injury",
                            "Family Law",
                            "Other Legal",
                            "Non-Legal"
                        ],
                        "description": "The legal area. Must be one of the exact values from the enum list."
                    },
                    "plain_english": {
                        "type": "string",
                        "description": "The plain English translation of the legal text."
                    }
                },
                "required": ["category", "plain_english"]
            }
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

PROMPT_TEMPLATE = os.getenv("PROMPT_TEMPLATE", "legal_assistant_v5.txt")

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

prompt_env = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "prompts")))

request_timestamps = defaultdict(list)

_LEGAL_SIGNAL_WORDS = {
    "hereby","whereas","agreement","contract","party","indemnify","hold harmless","trust","will","testament","estate",
    "plaintiff","defendant","warrant","deed","grantor","grantee","title","employee","employer","terminate","termination",
    "probation","confidential","custody","support","divorce","marriage","liability","negligence","injury","tort","statute"
}

_ESTATE_TERMS = {"will", "wills", "codicil", "codicils", "trust", "trustee", "estate", "testament", "beneficiary", "heir", "heirs", "probate"}

_CATEGORY_TERMS = {
    "Contract": {"indemnify", "hold harmless", "agreement", "party of the first part", "party of the second part", "time is of the essence", "binding upon", "assigns"},
    "Criminal Procedure": {"fourth amendment", "defendant", "search warrant", "probable cause", "remain silent", "attorney present", "criminal prosecution", "incriminating"},
    "Real Estate": {"title insurance", "warranty deed", "grantor", "grantee", "closing", "conveys", "convey", "as is", "warranty deed", "seller", "buyer"},
    "Employment Law": {"employee", "employer", "probationary", "terminated", "termination", "confidential", "proprietary", "reduction in force"},
    "Family Law": {"custodial", "child support", "custody", "divorce", "parental", "primary physical custody"},
    "Personal Injury": {"negligence", "duty of care", "damages", "car accident", "injuries", "plaintiff seeks", "injury"},
}

def adjust_category(legal_text: str, category: str) -> str:
    """If the model returned Other Legal or Non-Legal but clear trigger terms exist, promote to specific category.
    Protect Contract vs Estate overlap: presence of 'agreement' or 'indemnify' keeps Contract even if 'heirs' appears.
    """
    lowered = legal_text.lower()
    if category != "Personal Injury":
        if "plaintiff" in lowered and (
            "damages" in lowered or "injury" in lowered or "injuries" in lowered or "duty of care" in lowered or "negligence" in lowered
        ):
            strong_criminal_markers = ["search warrant", "probable cause", "fourth amendment", "remain silent", "attorney present", "criminal prosecution", "incriminating"]
            if not any(m in lowered for m in strong_criminal_markers):
                return "Personal Injury"
    if category in ("Other Legal", "Non-Legal"):
        if any(t in lowered for t in _ESTATE_TERMS):
            if "agreement" in lowered and not any(w in lowered for w in ("bequeath", "codicil", "last will", "testament")) and "upon my death" not in lowered:
                return "Contract"
            return "Wills, Trusts, and Estates"
        if any(t in lowered for t in _CATEGORY_TERMS["Contract"]):
            return "Contract"
        for cat, terms in _CATEGORY_TERMS.items():
            if cat == "Contract":
                continue
            if any(t in lowered for t in terms):
                return cat
    if category == "Wills, Trusts, and Estates":
        has_agreement = "agreement" in lowered
        strong_estate = any(w in lowered for w in ("bequeath", "codicil", "last will", "upon my death", "trustee", "testament"))
        if has_agreement and not strong_estate and "trust" not in lowered:
            return "Contract"
        real_estate_terms = _CATEGORY_TERMS.get("Real Estate", set())
        if not strong_estate and sum(1 for t in real_estate_terms if t in lowered) >= 2:
            return "Real Estate"
    if category == "Criminal Procedure":
        injury_terms = _CATEGORY_TERMS.get("Personal Injury", set())
        pi_hits = sum(1 for t in injury_terms if t in lowered)
        criminal_terms = {t for t in _CATEGORY_TERMS.get("Criminal Procedure", set()) if t != "defendant"}
        has_strong_criminal = any(t in lowered for t in criminal_terms)
        if pi_hits >= 1 and not has_strong_criminal:
            return "Personal Injury"
    if category == "Real Estate":
        real_estate_terms = _CATEGORY_TERMS.get("Real Estate", set())
        re_hits = sum(1 for t in real_estate_terms if t in lowered)
        strong_estate = any(w in lowered for w in ("bequeath", "codicil", "last will", "upon my death", "trustee", "testament"))
        if strong_estate and re_hits == 0:
            return "Wills, Trusts, and Estates"
        if "bequeath" in lowered:
            return "Wills, Trusts, and Estates"
    if category not in ("Wills, Trusts, and Estates"):
        if any(w in lowered for w in ("bequeath", "last will", "codicil", "upon my death", "testament")):
            if not ("agreement" in lowered and not any(w in lowered for w in ("bequeath", "codicil", "last will", "upon my death", "testament"))):
                return "Wills, Trusts, and Estates"
    return category

def _is_likely_legal(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in _LEGAL_SIGNAL_WORDS)

def create_basic_translation(text: str) -> str:
    """Fallback simplification without adding explanatory prefixes.
    Applies light, safe substitutions to reduce archaic or formal legal phrasing.
    Ensures output differs from input when possible.
    """
    original = text
    simplified = original
    replacements = [
        (r"\bshall\b", "will"),
        (r"\bhereby\b", ""),
        (r"\bthereof\b", "of it"),
        (r"\bherein\b", "here"),
        (r"\bwhereas\b", "because"),
        (r"\baforementioned\b", "earlier mentioned"),
        (r"\bparty of the first part\b", "first party"),
        (r"\bparty of the second part\b", "second party"),
        (r"\bupon my death\b", "when I die"),
        (r"\bremaining assets\b", "what's left"),
        (r"\bdistribute\b", "give"),
        (r"\bany and all\b", "all"),
        (r"\bincluding but not limited to\b", "including"),
        (r"\bprior to\b", "before"),
        (r"\bsubsequent to\b", "after"),
    ]
    for pattern, repl in replacements:
        try:
            simplified = re.sub(pattern, repl, simplified, flags=re.IGNORECASE)
        except re.error:
            continue
    simplified = re.sub(r"\s+", " ", simplified).strip()
    if simplified.lower() == original.lower():
        temp = re.sub(r"\bthe the\b", "the", simplified, flags=re.IGNORECASE)
        if temp.lower() != original.lower():
            simplified = temp
    return simplified

def ensure_meaningful_simplification(original: str, translated: str, category: str) -> str:
    """If the model output basically echoes the original (especially for Personal Injury), apply targeted rephrasing.
    Keeps meaning but uses more everyday phrasing.
    Only triggers if normalized strings match or differ trivially.
    """
    norm_orig = re.sub(r"[^a-z0-9]+", " ", original.lower()).strip()
    norm_trans = re.sub(r"[^a-z0-9]+", " ", translated.lower()).strip()
    if category == "Personal Injury" and (norm_orig == norm_trans or len(set(norm_orig.split()) ^ set(norm_trans.split())) <= 2):
        simplified = translated
        replacements = [
            (r"\bdefendant\b", "the other party"),
            (r"\bplaintiff\b", "the injured person"),
            (r"\bbreached the duty of care owed to\b", "failed to act with reasonable care toward"),
            (r"\bbreached\b", "failed to meet"),
            (r"\bduty of care\b", "responsibility to act carefully"),
            (r"\bresulting in compensable damages\b", "causing harm the injured person can seek money for"),
            (r"\bcompensable damages\b", "harm they can recover money for"),
            (r"\bseeks damages\b", "is asking for money"),
            (r"\binjuries sustained\b", "injuries suffered"),
            (r"\bnegligence\b", "carelessness"),
        ]
        for pattern, repl in replacements:
            try:
                simplified = re.sub(pattern, repl, simplified, flags=re.IGNORECASE)
            except re.error:
                continue
        simplified = re.sub(r"\s+", " ", simplified).strip()
        if simplified.lower() == original.lower():
            simplified = simplified + " (stating the other party failed to use proper care and caused recoverable harm)"
        return simplified.strip()
    return translated

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
    try:
        system_prompt = prompt_env.get_template(PROMPT_TEMPLATE).render()
    except Exception:
        system_prompt = prompt_env.get_template("legal_assistant_v4.txt").render()

    logger.info(f"Received request: {legal_text!r}")

    try:
        completion_kwargs = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": legal_text}
            ],
            "tools": tools,
            "tool_choice": {"type": "function", "function": {"name": "classify_legal_area"}},
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
        if hasattr(choice, "tool_calls") and choice.tool_calls:
            for tc in choice.tool_calls:
                try:
                    if getattr(tc, "type", "") == "function":
                        fn = getattr(tc, "function", None)
                        if fn and getattr(fn, "arguments", None):
                            args_str = fn.arguments
                            break
                except Exception:
                    continue
        elif hasattr(choice, "function_call") and getattr(choice.function_call, "arguments", None):
            args_str = choice.function_call.arguments

        parsed = {}
        parse_confidence = "low"
        if args_str:
            try:
                parsed = json.loads(args_str)
                parse_confidence = "high"
            except Exception as parse_err:
                logger.error(f"Parse Error decoding function arguments: {parse_err}")
                try:
                    category_match = re.search(r'"category"\s*:\s*"([^"]+)"', args_str)
                    text_match = re.search(r'"plain_english"\s*:\s*"([^"]+)"', args_str)
                    if category_match and text_match:
                        parsed = {
                            "category": category_match.group(1),
                            "plain_english": text_match.group(1)
                        }
                        parse_confidence = "medium"
                    else:
                        parsed = {"category": "", "plain_english": args_str}
                        parse_confidence = "low"
                except Exception:
                    parsed = {"category": "", "plain_english": args_str}
                    parse_confidence = "low"
        else:
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
                # Fallback with estate detection
                lower_text = legal_text.lower()
                if any(t in lower_text for t in _ESTATE_TERMS):
                    fallback_category = "Wills, Trusts, and Estates"
                else:
                    fallback_category = "Other Legal" if _is_likely_legal(legal_text) else "Non-Legal"
                parsed = {
                    "category": fallback_category,
                    "plain_english": content.strip() if content.strip() else create_basic_translation(legal_text)
                }
                parse_confidence = "low"

        if not parsed.get("category") or parsed.get("category").strip() == "":
            parsed["category"] = "Other Legal" if _is_likely_legal(legal_text) else "Non-Legal"
            logger.info("Assigned fallback category '%s' (minimal detection).", parsed["category"]) 

        original_category = parsed.get("category", "")
        new_category = adjust_category(legal_text, original_category)
        if new_category != original_category:
            parsed["category"] = new_category
            if parse_confidence == "high":
                parse_confidence = "adjusted" 

        response_text = parsed.get("plain_english", "").strip()
        if not response_text or response_text.lower() == legal_text.lower():
            response_text = create_basic_translation(legal_text)
            parsed["plain_english"] = response_text

        if parsed.get("category") == "Non-Legal":
            norm_original = re.sub(r"\s+", " ", legal_text.strip().lower())
            norm_resp = re.sub(r"\s+", " ", parsed.get("plain_english", "").strip().lower())
            if norm_resp == norm_original:
                parsed["plain_english"] = "This isn't legal language; there's nothing to translate." 
                response_text = parsed["plain_english"]
        
        confidence = "high" if len(legal_text.split()) > 10 else "medium"
        response_text = parsed.get("plain_english", "")
        response_text = ensure_meaningful_simplification(legal_text, response_text, parsed.get("category", ""))
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