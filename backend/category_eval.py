import requests
import yaml

API_URL = "http://localhost:8000/simplify"

def load_samples(path):
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data["samples"]

def run_eval(samples):
    correct = 0
    for sample in samples:
        response = requests.post(API_URL, json={"text": sample["input"]})
        data = response.json()
        predicted = data.get("category", "").strip()
        expected = sample["expected_category"].strip()
        print(f"Input: {sample['input']}")
        print(f"Expected: {expected}, Got: {predicted}")
        if predicted == expected:
            correct += 1
    print(f"\nAccuracy: {correct}/{len(samples)} ({100 * correct / len(samples):.1f}%)")

if __name__ == "__main__":
    samples = load_samples("category_eval_samples.yaml")
    run_eval(samples)