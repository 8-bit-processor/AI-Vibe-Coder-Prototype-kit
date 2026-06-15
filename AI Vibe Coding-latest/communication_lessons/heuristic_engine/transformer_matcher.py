"""
Module: transformer_matcher.py
Description: Optional module for semantic similarity using sentence-transformers.
             Decoupled from core to keep the facade fast and portable.
"""

from typing import List, Tuple

class TransformerMatcher:
    """
    Semantic similarity matcher using Transformer embeddings.
    """
    def __init__(self):
        # Lazy import: Only attempt to load if needed.
        # Requires: pip install sentence-transformers
        from sentence_transformers import SentenceTransformer, util
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.exemplar_embeddings = {}

    def prepare_exemplars(self, rule_name: str, exemplars: List[str]):
        """Caches embeddings for rules."""
        self.exemplar_embeddings[rule_name] = self.model.encode(exemplars, convert_to_tensor=True)

    def calculate_similarity(self, text: str, rule_name: str, exemplars: List[str]) -> float:
        """Calculates semantic similarity between text and a rule's cached exemplars."""
        from sentence_transformers import util
        
        if rule_name not in self.exemplar_embeddings:
            self.prepare_exemplars(rule_name, exemplars)
            
        text_embedding = self.model.encode(text, convert_to_tensor=True)
        # Compute cosine similarities
        cosine_scores = util.cos_sim(text_embedding, self.exemplar_embeddings[rule_name])
        
        return float(cosine_scores.max())
