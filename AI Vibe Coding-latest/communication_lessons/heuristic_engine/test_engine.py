"""
Standalone test for the Heuristic Rule Engine.
Verifies Hard Rules, Similarity, and Learning mechanism.
"""

from communication_lessons.heuristic_engine import HeuristicRuleEngine
import json

def test_engine():
    engine = HeuristicRuleEngine()
    
    # 1. Test Hard Rule (Rename)
    print("Testing Hard Rule...")
    text1 = "I think you should rename space invaders.py to spaceinvaders.py"
    matches1 = engine.evaluate(text1)
    print(f"Input: '{text1}'")
    print(f"Matches: {matches1}")
    
    # 2. Test Similarity (Support Mode)
    print("\nTesting Similarity...")
    text2 = "Try to open your editor and click save after pasting."
    
    # Debug: see actual scores
    for rule in engine.rules:
        if rule['name'] == "Support Mode Refocus":
            best_m, score = engine.transformer.find_best_match(text2, rule['similarity_exemplars'])
            print(f"Debug: Best match for 'Support Mode Refocus': '{best_m}' (Score: {score:.2f})")
    
    matches2 = engine.evaluate(text2)
    print(f"Input: '{text2}'")
    print(f"Matches: {matches2}")
    
    # 3. Test Learning
    print("\nTesting Learning Mechanism...")
    novel_text = "Go ahead and modify the filename to remove the space char."
    print(f"Initial evaluation of novel text: {engine.evaluate(novel_text)}")
    
    print("Learning the novel pattern for 'Rename Recommendation'...")
    engine.learn_new_pattern("Rename Recommendation", novel_text)
    
    print(f"Evaluation after learning: {engine.evaluate(novel_text)}")
    
    # 4. Verify rules.json readability
    print("\nVerifying rules.json updates...")
    with open(engine.rules_path, 'r') as f:
        data = json.load(f)
        for rule in data['rules']:
            if rule['name'] == "Rename Recommendation":
                print(f"Exemplars in 'Rename Recommendation': {len(rule['similarity_exemplars'])}")
                if novel_text in rule['similarity_exemplars']:
                    print("SUCCESS: Novel pattern captured in JSON.")

if __name__ == "__main__":
    test_engine()
