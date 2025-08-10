import requests
import yaml
import json
from openai import OpenAI
import os
from dotenv import load_dotenv
import time
import sys
import math
from typing import Any, Dict, List

load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:8000") + "/simplify"
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EVAL_REQUEST_TIMEOUT = float(os.getenv("EVAL_REQUEST_TIMEOUT", "25"))  # seconds per backend call
EVAL_MAX_RETRIES = int(os.getenv("EVAL_MAX_RETRIES", "3"))
EVAL_RETRY_BACKOFF = float(os.getenv("EVAL_RETRY_BACKOFF", "1.5"))
SKIP_QUALITY = os.getenv("SKIP_QUALITY", "false").lower() in {"1", "true", "yes"}
EVAL_MODEL = os.getenv("EVAL_MODEL", "gpt-4")  # or gpt-5 variant
EVAL_RESULTS_PATH = os.getenv("EVAL_RESULTS_PATH", "enhanced_eval_results.json")

def wait_for_server(max_retries=None, delay=1):
    """Wait for the server to be ready"""
    base_url = os.getenv("API_URL", "http://localhost:8000")
    health_url = base_url + "/health"
    
    if max_retries is None:
        if "localhost" in base_url:
            max_retries = 30
        else:
            max_retries = 180
            delay = 2

    print(f"Checking if server is ready at {base_url}...")
    if "onrender.com" in base_url:
        print("Note: Render deployments can take 1-2 minutes...")

    for i in range(max_retries):
        try:
            response = requests.get(health_url, timeout=10)
            if response.status_code == 200:
                print(f"✅ Server is ready after {i * delay} seconds!")
                return True
        except requests.exceptions.RequestException:
            pass
        
        if i < max_retries - 1:
            if i % 10 == 0:
                print(f"Still waiting... ({(i+1) * delay}s/{max_retries * delay}s)")
            time.sleep(delay)
    
    print(f"❌ Server not responding after {max_retries * delay} seconds")
    return False

def load_samples(path):
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data["samples"]

def evaluate_translation_quality(original: str, translation: str) -> int:
    """Use the model to evaluate translation quality (1-5)."""
    prompt = f"""
Evaluate this legal translation on a scale of 1-5 ONLY RESPOND WITH THE NUMBER:\n\nOriginal: {original}\nTranslation: {translation}\n\nCriteria:\n1. Accuracy (preserves legal meaning)\n2. Clarity (easy to understand)\n3. Completeness (doesn't omit important details)\n\nRespond with just an integer 1-5.
"""
    try:
        kwargs = {
            "model": EVAL_MODEL,
            "messages": [{"role": "user", "content": prompt}],
        }
        if EVAL_MODEL.startswith("gpt-5"):
            kwargs["max_completion_tokens"] = 10
        else:
            kwargs["max_tokens"] = 10
            kwargs["temperature"] = 0
        resp = client.chat.completions.create(**kwargs)
        raw = (resp.choices[0].message.content or "").strip()
        score = int(''.join(ch for ch in raw if ch.isdigit())[:1] or '3')
        return max(1, min(5, score))
    except Exception:
        return 3

def backend_request_with_retries(payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST to backend /simplify with retries & backoff; returns JSON or raises last error."""
    last_err = None
    for attempt in range(1, EVAL_MAX_RETRIES + 1):
        try:
            r = requests.post(API_URL, json=payload, timeout=EVAL_REQUEST_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            last_err = e
            if attempt < EVAL_MAX_RETRIES:
                sleep_for = (EVAL_RETRY_BACKOFF ** (attempt - 1))
                print(f"    Retry {attempt}/{EVAL_MAX_RETRIES-1} after error: {e} (sleep {sleep_for:.1f}s)")
                time.sleep(sleep_for)
            else:
                break
    raise last_err if last_err else RuntimeError("Unknown request failure")

def run_comprehensive_eval(samples):
    category_correct = 0
    quality_scores = []
    results = []
    
    print("Running comprehensive evaluation...\n")
    
    start_time = time.time()
    for i, sample in enumerate(samples, 1):
        print(f"[{i}/{len(samples)}] Testing: {sample['input'][:50]}...")
        per_start = time.time()
        try:
            data = backend_request_with_retries({"text": sample["input"]})
            predicted_category = data.get("category", "").strip()
            translation = data.get("response", "").strip()
        except Exception as e:
            print(f"  ❌ API Error after retries: {e}")
            results.append({
                "input": sample["input"],
                "expected_category": sample["expected_category"],
                "predicted_category": "",
                "category_correct": False,
                "translation": "",
                "quality_score": None,
                "error": str(e)
            })
            continue

        expected_category = sample["expected_category"].strip()
        category_match = predicted_category == expected_category
        if category_match:
            category_correct += 1

        quality_score = None
        if not SKIP_QUALITY and expected_category != "Other" and translation:
            quality_score = evaluate_translation_quality(sample["input"], translation)
            quality_scores.append(quality_score)

        result = {
            "input": sample["input"],
            "expected_category": expected_category,
            "predicted_category": predicted_category,
            "category_correct": category_match,
            "translation": translation,
            "quality_score": quality_score
        }
        results.append(result)

        status = "✅" if category_match else "❌"
        quality_str = f" | Quality: {quality_score}/5" if quality_score else ""
        elapsed = time.time() - per_start
        avg_so_far = (time.time() - start_time) / i
        eta = avg_so_far * (len(samples) - i)
        print(f"  {status} Expected: {expected_category}, Got: {predicted_category}{quality_str} | {elapsed:.1f}s (ETA ~{eta:.1f}s)")

    print("\n" + "="*60)
    print("EVALUATION RESULTS")
    print("="*60)
    
    category_accuracy = (category_correct / len(samples)) * 100
    print(f"Category Accuracy: {category_correct}/{len(samples)} ({category_accuracy:.1f}%)")
    
    if quality_scores:
        avg_quality = sum(quality_scores) / len(quality_scores)
        print(f"Average Translation Quality: {avg_quality:.2f}/5.0")
        print(f"Quality Distribution: {dict(zip(*zip(*[(score, quality_scores.count(score)) for score in range(1, 6) if score in quality_scores])))}")
    
    failed_categories = {}
    for result in results:
        if not result["category_correct"]:
            expected = result["expected_category"]
            predicted = result["predicted_category"]
            key = f"{expected} → {predicted}"
            failed_categories[key] = failed_categories.get(key, 0) + 1
    
    if failed_categories:
        print("\nMost Common Category Errors:")
        for error, count in sorted(failed_categories.items(), key=lambda x: x[1], reverse=True):
            print(f"  {error}: {count} times")
    
    failures = [r for r in results if r.get("error")] 
    if failures:
        print(f"\nErrors encountered on {len(failures)} samples (kept going). Set EVAL_MAX_RETRIES higher or increase EVAL_REQUEST_TIMEOUT to mitigate timeouts.")
    print("\nConfig used:")
    print(f"  Timeout: {EVAL_REQUEST_TIMEOUT}s | Retries: {EVAL_MAX_RETRIES} | Backoff: {EVAL_RETRY_BACKOFF} | Skip quality: {SKIP_QUALITY} | Eval model: {EVAL_MODEL}")
    # Persist results to JSON for CI reuse / parsing
    try:
        summary = {
            "total_samples": len(samples),
            "category_correct": category_correct,
            "accuracy": category_accuracy / 100.0,
            "average_quality": (sum(quality_scores) / len(quality_scores)) if quality_scores else None,
            "timestamp": time.time(),
            "model": EVAL_MODEL,
            "skip_quality": SKIP_QUALITY
        }
        with open(EVAL_RESULTS_PATH, "w") as f:
            json.dump({"summary": summary, "results": results}, f, indent=2)
        print(f"Saved evaluation results to {EVAL_RESULTS_PATH}")
    except Exception as e:
        print(f"Warning: failed to write results file: {e}")
    return results

if __name__ == "__main__":
    if not wait_for_server():
        base_url = os.getenv("API_URL", "http://localhost:8000")
        print(f"❌ Cannot connect to backend server at {base_url}")
        if "localhost" in base_url:
            print("Make sure the server is running with: uvicorn main:app --reload --port 8000")
        else:
            print("Check that the production server is accessible and running")
        sys.exit(1)
    
    samples = load_samples("category_eval_samples.yaml")
    results = run_comprehensive_eval(samples)
