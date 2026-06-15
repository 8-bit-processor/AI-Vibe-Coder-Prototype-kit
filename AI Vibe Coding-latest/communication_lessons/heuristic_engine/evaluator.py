"""
Module: evaluator.py
Description: The decision engine for the Heuristic Rule Engine. 
             Handles hierarchical matching and autonomous learning by appending 
             new exemplars to the human-readable rules.json.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from rich.console import Console
from .similarity_transformer import SimilarityTransformer

console = Console()

class HeuristicRuleEngine:
    """
    Evaluates LLM output against a set of human-readable rules using 
    both exact matching and semantic similarity.
    """

    def __init__(self, rules_path: Optional[Path] = None):
        """
        Initializes the engine and loads the rules from JSON.
        """
        if rules_path is None:
            self.rules_path = Path(__file__).parent / "data" / "rules.json"
        else:
            self.rules_path = rules_path
            
        self.transformer = SimilarityTransformer()
        self.data = self._load_data()
        self.rules = self.data.get("rules", [])
        self.transformer_enabled = self.data.get("transformer_enabled", False)

    def _load_data(self) -> Dict[str, Any]:
        """Loads data from the JSON file."""
        if self.rules_path.exists():
            with open(self.rules_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"transformer_enabled": False, "rules": []}

    def _get_transformer_model(self):
        """Lazy loads the transformer model."""
        if not self.transformer_enabled:
            return None
        try:
            from .transformer_matcher import TransformerMatcher
            if not hasattr(self, '_transformer_model'):
                self._transformer_model = TransformerMatcher()
            return self._transformer_model
        except ImportError:
            console.print("[yellow]Warning: sentence-transformers not installed. Transformer matching disabled.[/yellow]")
            return None

    def _save_rules(self):
        """Persists rules back to the JSON file."""
        with open(self.rules_path, 'w', encoding='utf-8') as f:
            json.dump({"transformer_enabled": self.transformer_enabled, "rules": self.rules}, f, indent=2)

    def evaluate(self, text: str) -> List[Dict[str, Any]]:
        """
        Evaluates the text against all rules using the hierarchy:
        1. Hard Rules (Regex)
        2. Similarity Transformer (Keyword)
        3. Semantic Transformer (Optional)
        
        Returns:
            List[Dict[str, Any]]: Actions triggered by matching rules.
        """
        triggered_actions = []
        transformer = self._get_transformer_model()

        for rule in self.rules:
            matched = False
            
            # Level 1: Hard Rules (Regex)
            for pattern in rule.get("hard_rules", []):
                if re.search(pattern, text, re.IGNORECASE):
                    matched = True
                    break
            
            # Level 2: Keyword-based Similarity
            if not matched:
                exemplars = rule.get("similarity_exemplars", [])
                if exemplars:
                    best_match, score = self.transformer.find_best_match(text, exemplars)
                    if score >= rule.get("threshold", 0.75):
                        matched = True

            # Level 3: Semantic Transformer Similarity
            if not matched and transformer:
                 exemplars = rule.get("similarity_exemplars", [])
                 if exemplars:
                     score = transformer.calculate_similarity(text, rule["name"], exemplars)
                     if score >= rule.get("threshold", 0.75):
                         matched = True
            
            if matched:
                action = {
                    "action": rule.get("action"),
                    "name": rule.get("name"),
                    "params": rule.get("params", {})
                }
                triggered_actions.append(action)

        return triggered_actions

    def learn_new_pattern(self, rule_name: str, text: str):
        """
        Appends a new exemplar to a specific rule, enabling autonomous learning.
        
        Args:
            rule_name (str): The name of the rule to update.
            text (str): The LLM response text that should be learned.
        """
        for rule in self.rules:
            if rule["name"] == rule_name:
                if "similarity_exemplars" not in rule:
                    rule["similarity_exemplars"] = []
                
                # Avoid duplicates
                if text not in rule["similarity_exemplars"]:
                    rule["similarity_exemplars"].append(text)
                    self._save_rules()
                    return True
        return False

    def create_rule(self, name: str, action: str, hard_rules: List[str] = None):
        """
        Manually creates a new rule in the dictionary.
        """
        new_rule = {
            "name": name,
            "action": action,
            "hard_rules": hard_rules or [],
            "similarity_exemplars": [],
            "threshold": 0.75
        }
        self.rules.append(new_rule)
        self._save_rules()
