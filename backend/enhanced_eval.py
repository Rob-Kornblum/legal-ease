import requests
import yaml
import json
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = "http://localhost:8000/simplify"
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def load_samples(path):
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data["samples"]

def evaluate_translation_quality(original, translation):
    """Use GPT to evaluate if the translation is accurate and clear"""
    prompt = f"""
    Evaluate this legal translation on a scale of 1-5:
    
    Original: {original}
    Translation: {translation}
    
    Rate the translation based on:
    1. Accuracy (preserves legal meaning)
    2. Clarity (easy to understand)
    3. Completeness (doesn't omit important details)
    
    Respond with just a number 1-5, where:
    1 = Poor, 2 = Below Average, 3 = Good, 4 = Very Good, 5 = Excellent
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0
        )
        score = int(response.choices[0].message.content.strip())
        return max(1, min(5, score))
    except:
        return 3

def run_comprehensive_eval(samples):
    category_correct = 0
    quality_scores = []
    results = []
    
    print("Running comprehensive evaluation...\n")
    
    for i, sample in enumerate(samples, 1):
        print(f"[{i}/{len(samples)}] Testing: {sample['input'][:50]}...")
        
        try:
            response = requests.post(API_URL, json={"text": sample["input"]})
            data = response.json()
            predicted_category = data.get("category", "").strip()
            translation = data.get("response", "").strip()
        except Exception as e:
            print(f"  ❌ API Error: {e}")
            continue
        
        expected_category = sample["expected_category"].strip()
        category_match = predicted_category == expected_category
        if category_match:
            category_correct += 1
        
        quality_score = None
        if expected_category != "Other" and translation:
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
        print(f"  {status} Expected: {expected_category}, Got: {predicted_category}{quality_str}")

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
    
    return results

if __name__ == "__main__":
    samples = load_samples("category_eval_samples.yaml")
    results = run_comprehensive_eval(samples)
