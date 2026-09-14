"""
Markdown SEARCH/REPLACE and Code Block Parser (Aider-compatible).
Enables local models to output natural code diffs without JSON escaping issues.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class DiffBlock:
    def __init__(self, file_path: str, search_text: str, replace_text: str):
        self.file_path = file_path.strip()
        self.search_text = search_text
        self.replace_text = replace_text


class NewFileBlock:
    def __init__(self, file_path: str, content: str):
        self.file_path = file_path.strip()
        self.content = content


def extract_search_replace_blocks(text: str) -> List[DiffBlock]:
    """
    Extracts Aider-style SEARCH/REPLACE blocks from text.
    Format:
        filename.ext
        <<<<<<< SEARCH
        exact lines to find
        =======
        new replacement lines
        >>>>>>> REPLACE
    """
    blocks = []
    # Pattern matching file path followed by SEARCH/REPLACE markers
    pattern = re.compile(
        r"(?:(?:File|Path|Update)?[:`\s]*([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9]+)[`\s]*\n)?"
        r"<<<<<<<\s*SEARCH\r?\n(.*?)\r?\n=======\r?\n(.*?)\r?\n>>>>>>>\s*REPLACE",
        re.DOTALL
    )

    last_file = ""
    for match in pattern.finditer(text):
        file_candidate = match.group(1)
        search_chunk = match.group(2)
        replace_chunk = match.group(3)

        if file_candidate:
            last_file = file_candidate.strip().strip("`").strip()

        # If file path wasn't right above the block, look back a few lines
        if not file_candidate and not last_file:
            start_pos = match.start()
            preceding_text = text[max(0, start_pos - 200):start_pos]
            file_match = re.findall(r"[`'\"]([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9]+)[`'\"]", preceding_text)
            if file_match:
                last_file = file_match[-1]

        if last_file:
            blocks.append(DiffBlock(last_file, search_chunk, replace_chunk))

    return blocks


def extract_new_file_blocks(text: str) -> List[NewFileBlock]:
    """
    Extracts markdown code blocks explicitly marked with a filename.
    Format:
        ```python file="path/to/file.py"
        ...content...
        ```
        or
        Create `path/to/file.py`:
        ```python
        ...content...
        ```
    """
    blocks = []

    # 1. ```lang file="path.py"
    pattern1 = re.compile(
        r"```[a-zA-Z0-9_-]*\s+(?:file|path)=[\"']([^\"']+)[\"']\r?\n(.*?)\r?\n```",
        re.DOTALL
    )
    for match in pattern1.finditer(text):
        file_path = match.group(1).strip()
        content = match.group(2)
        if "<<<<<<< SEARCH" not in content:
            blocks.append(NewFileBlock(file_path, content))

    # 2. File: `path.py` followed immediately by ```...```
    pattern2 = re.compile(
        r"(?:Create|Write to|File|Path)?[:`\s]+[`']([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9]+)[`']\s*:\s*\r?\n```[a-zA-Z0-9_-]*\r?\n(.*?)\r?\n```",
        re.DOTALL
    )
    for match in pattern2.finditer(text):
        file_path = match.group(1).strip()
        content = match.group(2)
        if "<<<<<<< SEARCH" not in content:
            blocks.append(NewFileBlock(file_path, content))

    return blocks
