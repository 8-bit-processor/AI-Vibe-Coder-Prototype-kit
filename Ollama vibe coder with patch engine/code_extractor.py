# code_extractor.py
from typing import List, Tuple
import re

def extract_code_blocks(text: str) -> List[str]:
    """
    Extracts content from markdown code blocks. 
    Handles ```python, ```py, ```javascript, ```js, ```markdown or just ```.
    If no backticks are found, but the content looks like code (starts with imports or comments),
    it returns the entire text as a single block.
    """
    # More flexible pattern to capture various languages and generic blocks
    pattern = r"```(?:\w+)?\s*(?:\n---.*?---\s*)?\n(.*?)\n```"
    blocks = re.findall(pattern, text, re.DOTALL)
    
    if not blocks:
        # Heuristic: If it looks like a full file and has no backticks, treat whole thing as code
        if text.strip().startswith(("import ", "from ", "#", '"""', "'''", "def ", "class ")):
            return [text.strip()]
            
    return blocks

def extract_code_blocks_with_filenames(text: str) -> List[Tuple[str, str]]:
    """
    Extracts code blocks along with potential filenames.
    Returns a list of tuples: (filename, code_content)
    """
    blocks_with_filenames = []
    
    # 1. Find all code blocks
    block_pattern = r"(?:(?:^|\n)([^\n]*)\n)?```(?:\w+)?\s*\n(.*?)\n```"
    matches = list(re.finditer(block_pattern, text, re.DOTALL))
    
    if not matches:
        # Fallback for no backticks
        code_blocks = extract_code_blocks(text)
        if code_blocks:
            # For the fallback case, try to find the filename in the entire text
            filename = ""
            file_hints = [
                r"(?:file|filename|save to|create|path|into):\s*([a-zA-Z0-9_\-\./]+)",
                r"###\s*([a-zA-Z0-9_\-\./]+)",
                r"\*\*([a-zA-Z0-9_\-\./]+)\*\*",
                r"([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)"
            ]
            for hint_pat in file_hints:
                hint_match = re.search(hint_pat, text, re.IGNORECASE)
                if hint_match:
                    filename = hint_match.group(1).strip()
                    break
            
            # If still not found, check the first few lines of the code itself
            if not filename:
                first_lines = code_blocks[0].split('\n')[:3]
                for line in first_lines:
                    comment_match = re.search(r"(?:#|//)\s*([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)", line)
                    if comment_match:
                        filename = comment_match.group(1).strip()
                        break
            
            return [(filename, code_blocks[0])]
    
    for match in matches:
        preceding_text = match.group(1) or ""
        code_content = match.group(2)
        filename = ""
        
        # Try to find filename in preceding text
        file_hints = [
            r"(?:file|filename|save to|create|path|into):\s*([a-zA-Z0-9_\-\./]+)",
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
                comment_match = re.search(r"(?:#|//)\s*([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)", line)
                if comment_match:
                    filename = comment_match.group(1).strip()
                    break
        
        blocks_with_filenames.append((filename, code_content))
        
    return blocks_with_filenames
