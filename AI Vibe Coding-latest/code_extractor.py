# code_extractor.py
from typing import List, Tuple
import re

def extract_code_blocks(text: str) -> List[Tuple[str, str]]:
    """
    Extracts language tags and content from Markdown code blocks in a given text.

    It captures the language tag (if any) and the content between triple 
    backticks (```).

    Args:
        text (str): The raw text response from the LLM.

    Returns:
        List[Tuple[str, str]]: A list of tuples, each containing (language, content).
    """
    # Pattern explanation:
    # 1. Matches ```
    # 2. Captures optional language tag (\w*)
    # 3. Matches optional whitespace/newline
    # 4. Non-greedily captures content (.*?) until the closing ```
    pattern = r"```(\w*)[\s\n]*(.*?)```"
    blocks = re.findall(pattern, text, re.DOTALL)
    
    if not blocks:
        # Fallback: Try to detect plain text code blocks if no backticks exist
        return extract_plain_text_code(text)
    
    return blocks

def extract_plain_text_code(text: str) -> List[Tuple[str, str]]:
    """
    Attempts to identify code blocks that are NOT wrapped in triple backticks.
    
    Looks for sequences of lines starting with imports or containing 
    class/def keywords.
    
    Args:
        text (str): The raw text response.
        
    Returns:
        List[Tuple[str, str]]: Detected code snippets as (language, content).
    """
    # Look for common Python start patterns
    python_patterns = [
        r"(?:^|\n)(import\s+\w+.*?)(?:\n\n|\n[a-zA-Z]|$)",
        r"(?:^|\n)(from\s+\w+.*?import.*?)(?:\n\n|\n[a-zA-Z]|$)",
        r"(?:^|\n)(class\s+\w+.*?:\s*\n.*?)(?:\n\n|\n[a-zA-Z]|$)",
        r"(?:^|\n)(def\s+\w+\(.*?\):\s*\n.*?)(?:\n\n|\n[a-zA-Z]|$)"
    ]
    
    found = []
    for pattern in python_patterns:
        matches = re.findall(pattern, text, re.DOTALL | re.MULTILINE)
        for match in matches:
            if len(match.splitlines()) > 3: # Minimum 3 lines to avoid noise
                found.append(("python", match.strip()))
                
    return found
