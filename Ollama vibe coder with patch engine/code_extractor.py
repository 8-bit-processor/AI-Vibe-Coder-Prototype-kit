# code_extractor.py
from typing import List, Tuple
import re

def extract_code_blocks(text: str) -> List[str]:
    """
    Extracts content from markdown code blocks. 
    Handles ```python, ```py, ```javascript, ```js, ```markdown or just ```.
    """
    # More flexible pattern to capture various languages and generic blocks
    pattern = r"```(?:\w+)?\s*(?:\n---.*?---\s*)?\n(.*?)\n```"
    return re.findall(pattern, text, re.DOTALL)

def extract_code_blocks_with_filenames(text: str) -> List[Tuple[str, str]]:
    """
    Extracts code blocks along with potential filenames.
    Returns a list of tuples: (filename, code_content)
    """
    # This pattern captures the block and some preceding text to look for filenames
    # We look for lines like "File: filename.py" or "### filename.py" or just "filename.py"
    # and also for comments inside the code block.
    
    blocks_with_filenames = []
    
    # 1. Find all code blocks
    block_pattern = r"(?:(?:^|\n)([^\n]*)\n)?```(?:\w+)?\s*\n(.*?)\n```"
    matches = re.finditer(block_pattern, text, re.DOTALL)
    
    for match in matches:
        preceding_text = match.group(1) or ""
        code_content = match.group(2)
        filename = ""
        
        # Try to find filename in preceding text
        # Patterns: "File: name.ext", "### name.ext", "**name.ext**", "name.ext"
        file_hints = [
            r"(?:file|filename|save to|path):\s*([a-zA-Z0-9_\-\./]+)",
            r"###\s*([a-zA-Z0-9_\-\./]+)",
            r"\*\*([a-zA-Z0-9_\-\./]+)\*\*",
            r"([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)"
        ]
        
        for hint_pat in file_hints:
            hint_match = re.search(hint_pat, preceding_text, re.IGNORECASE)
            if hint_match:
                filename = hint_match.group(1).strip()
                break
        
        # If not found, try to find filename in first few lines of code (as a comment)
        if not filename:
            first_lines = code_content.split('\n')[:3]
            for line in first_lines:
                # Python/JS/Shell comment pattern
                comment_match = re.search(r"(?:#|//)\s*([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)", line)
                if comment_match:
                    filename = comment_match.group(1).strip()
                    break
        
        blocks_with_filenames.append((filename, code_content))
        
    return blocks_with_filenames
