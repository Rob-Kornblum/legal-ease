"""
Performance monitoring script that tracks model performance over time
and alerts if performance degrades.
"""

import json
import datetime
from pathlib import Path
import subprocess
import sys

def run_evaluation():
    """Run the enhanced evaluation and return results"""
    try:
        result = subprocess.run([
            sys.executable, "enhanced_eval.py"
        ], capture_output=True, text=True, cwd="backend")
        
        if result.returncode != 0:
            print(f"Evaluation failed: {result.stderr}")
            return None
            
        output = result.stdout
        
        for line in output.split('\n'):
            if "Category Accuracy:" in line:
                parts = line.split(":")[-1].strip()
                correct, total = parts.split(" ")[0].split("/")
                accuracy = float(correct) / float(total)
                break
        else:
            return None
            
        for line in output.split('\n'):
            if "Average Translation Quality:" in line:
                quality = float(line.split(":")[1].strip().split("/")[0])
                break
        else:
            quality = None
            
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "category_accuracy": accuracy,
            "translation_quality": quality,
            "total_cases": int(total),
            "correct_cases": int(correct)
        }
        
    except Exception as e:
        print(f"Error running evaluation: {e}")
        return None

def save_results(results, filename="performance_history.json"):
    """Save results to a JSON file for tracking over time"""
    history_file = Path(filename)
    
    if history_file.exists():
        with open(history_file) as f:
            history = json.load(f)
    else:
        history = []
    
    history.append(results)
    
    with open(history_file, 'w') as f:
        json.dump(history, f, indent=2)
    
    return history

def check_performance_regression(history, min_accuracy=0.95, min_quality=4.0):
    """Check if performance has regressed below acceptable thresholds"""
    if not history:
        return True
        
    latest = history[-1]
    
    issues = []
    
    if latest["category_accuracy"] < min_accuracy:
        issues.append(f"Category accuracy {latest['category_accuracy']:.1%} below {min_accuracy:.1%}")
    
    if latest["translation_quality"] and latest["translation_quality"] < min_quality:
        issues.append(f"Translation quality {latest['translation_quality']:.2f} below {min_quality:.2f}")
    
    return issues

def main():
    print("🔍 Running Legal-Ease Performance Monitor...")
    
    results = run_evaluation()
    if not results:
        print("❌ Evaluation failed")
        sys.exit(1)
    
    history = save_results(results)
    
    print(f"✅ Evaluation completed:")
    print(f"   Category Accuracy: {results['category_accuracy']:.1%}")
    if results['translation_quality']:
        print(f"   Translation Quality: {results['translation_quality']:.2f}/5.0")
    
    issues = check_performance_regression(history)
    if issues:
        print("⚠️  Performance issues detected:")
        for issue in issues:
            print(f"   - {issue}")
        sys.exit(1)
    else:
        print("🎉 Performance looks good!")

    if len(history) > 1:
        prev = history[-2]
        accuracy_change = results['category_accuracy'] - prev['category_accuracy']
        print(f"📈 Accuracy trend: {accuracy_change:+.1%} from last run")
        
        if results['translation_quality'] and prev.get('translation_quality'):
            quality_change = results['translation_quality'] - prev['translation_quality']
            print(f"📈 Quality trend: {quality_change:+.2f} from last run")

if __name__ == "__main__":
    main()
