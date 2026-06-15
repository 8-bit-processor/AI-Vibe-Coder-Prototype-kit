"""
Module: similarity_transformer.py
Description: Implements keyword-vector similarity matching for the Heuristic Rule Engine.
             Inspired by t-bot (2021), it allows the facade to understand semantic 
             intent without exact regex matches.
"""

import re
from typing import List, Set, Dict

class SimilarityTransformer:
    """
    Transforms text into keyword vectors and calculates similarity scores.
    """
    
    def __init__(self, stop_words: Set[str] = None):
        """
        Initializes the transformer with an optional set of stop words to ignore.
        """
        self.stop_words = stop_words or {
            'a', 'an', 'the', 'is', 'are', 'was', 'were', 'to', 'for', 'in', 'on', 'at',
            'this', 'that', 'these', 'those', 'it', 'its', 'my', 'your', 'and', 'but',
            'or', 'so', 'if', 'then', 'else', 'when', 'how', 'why', 'what', 'who', 'whom'
        }

    def tokenize(self, text: str) -> List[str]:
        """
        Converts text into a list of lowercase alphanumeric tokens with basic stemming.
        """
        # Lowercase and remove punctuation
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        
        stemmed = []
        for t in tokens:
            if t in self.stop_words or len(t) <= 1:
                continue
            
            # Very basic suffix stripping for common endings
            if t.endswith('ing'): t = t[:-3]
            elif t.endswith('ed'): t = t[:-2]
            elif t.endswith('ies'): t = t[:-3] + 'y'
            elif t.endswith('s') and not t.endswith('ss'): t = t[:-1]
            
            stemmed.append(t)
            
        return stemmed

    def get_vector(self, tokens: List[str]) -> Dict[str, int]:
        """
        Converts a list of tokens into a frequency map (vector).
        """
        vector = {}
        for token in tokens:
            vector[token] = vector.get(token, 0) + 1
        return vector

    def calculate_similarity(self, text: str, exemplar: str) -> float:
        """
        Calculates a similarity score between 0.0 and 1.0 using Jaccard Similarity 
        on the keyword vectors.
        """
        tokens_text = set(self.tokenize(text))
        tokens_exemplar = set(self.tokenize(exemplar))
        
        if not tokens_exemplar:
            return 0.0
            
        intersection = tokens_text.intersection(tokens_exemplar)
        union = tokens_text.union(tokens_exemplar)
        
        # Jaccard similarity: size of intersection / size of union
        if not union:
            return 0.0
            
        score = len(intersection) / len(union)
        
        # Weighted bonus for keyword density (how much of the exemplar is covered)
        density_bonus = len(intersection) / len(tokens_exemplar)
        
        # Combined score (balanced average)
        return (score * 0.4) + (density_bonus * 0.6)

    def find_best_match(self, text: str, exemplars: List[str]) -> tuple[str, float]:
        """
        Finds the exemplar with the highest similarity score for the given text.

        Returns:
            tuple: (best_match_string, highest_score)
        """
        best_match = ""
        highest_score = 0.0
        
        for exemplar in exemplars:
            score = self.calculate_similarity(text, exemplar)
            if score > highest_score:
                highest_score = score
                best_match = exemplar
                
        return best_match, highest_score
