# code_extractor.py
from typing import List
import re

def extract_code_blocks(text: str) -> List[str]:
    """
    Extracts content from markdown code blocks. 
    Handles ```python, ```py, or just ```.
    """
    pattern = r"```(?:python|py)\s*(?:\n---.*?---\s*)?\n(.*?)\n```"
    return re.findall(pattern, text, re.DOTALL)
