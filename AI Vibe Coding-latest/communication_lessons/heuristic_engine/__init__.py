"""
Package: heuristic_engine
Description: Standalone intelligence module for the CLI facade.
             Inspired by t-bot (2021), it provides human-readable, 
             self-learning rules and similarity matching.
"""

from .similarity_transformer import SimilarityTransformer
from .evaluator import HeuristicRuleEngine

__all__ = ["SimilarityTransformer", "HeuristicRuleEngine"]
