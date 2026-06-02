"""
Utilities for extracting source code from LLM Markdown responses.

This module provides a robust, "forgiving" parser that isolates code blocks 
from raw text. It prioritizes the LLM's reasoning by being flexible with 
formatting variations while ensuring high-precision filename association using 
RapidFuzz for similarity matching.
"""

import re
import os
from typing import List, Tuple, Optional
from rapidfuzz import process, fuzz

def extract_code_blocks_with_filenames(text: str, preferred_filename: str = "main.py") -> List[Tuple[str, str]]:
    """
    Extracts code blocks and associates them with filenames using a multi-layered 
    heuristic approach powered by fuzzy matching.
    
    Layers:
    1. Explicit Metadata: ```python:filename.py
    2. Proximity Headers: Scans lines immediately preceding a block for file-like patterns.
    3. Neural/Fuzzy Anchoring: Uses RapidFuzz to match lines against potential filename patterns.
    """
    
    # Identify all triple-backtick blocks
    # Matches: ```[lang][:filename]\n[content]```
    block_pattern = r"```(?:\w+)?(?::[^\s\n]+)?\s*\n(.*?)\n```"
    blocks = list(re.finditer(block_pattern, text, re.DOTALL))
    
    extracted_files = []
    
    # Common code-related extensions to help validate filename-like strings
    VALID_EXTENSIONS = {'.py', '.js', '.ts', '.html', '.css', '.json', '.md', '.sh', '.yml', '.yaml', '.txt'}
    
    for i, match in enumerate(blocks):
        full_block_header = text[match.start():match.start() + 50].split('\n')[0]
        content = match.group(1)
        
        # --- LAYER 1: Explicit Tagging (```lang:filename.py) ---
        tag_match = re.match(r"```(?:\w+)?:([^\s\n]+)", full_block_header)
        if tag_match:
            extracted_files.append((tag_match.group(1), content))
            continue

        # --- LAYER 2 & 3: Proximity & Fuzzy Heuristics ---
        start_index = match.start()
        lookback_limit = 0
        if i > 0:
            lookback_limit = blocks[i-1].end()
            
        # Get the text between this block and the previous one (or start of text)
        preceding_text = text[max(lookback_limit, start_index - 500):start_index]
        lines = [line.strip() for line in preceding_text.split('\n') if line.strip()]
        
        # We focus on the last 5 non-empty lines closest to the block
        candidate_lines = lines[-5:]
        found_filename = None
        
        # We'll score each line based on how much it "looks like" a filename announcement
        best_score = 0
        
        for line in reversed(candidate_lines):
            # 1. Clean the line of common markdown flourishes
            clean_line = re.sub(r'^[#\*>\s\d\.\-]+', '', line) # Prefix cleanup
            clean_line = re.sub(r'[#\*>\s]+$', '', clean_line)   # Suffix cleanup
            
            # 2. Check for strong filename indicators (contains a dot + valid extension)
            _, ext = os.path.splitext(clean_line.lower())
            if ext in VALID_EXTENSIONS and ' ' not in clean_line:
                found_filename = clean_line
                break
                
            # 3. Fuzzy match against "File: [filename]" patterns
            # We look for words that end in our valid extensions
            words = clean_line.split()
            for word in words:
                clean_word = re.sub(r'[^\w\.\-\/]', '', word)
                _, w_ext = os.path.splitext(clean_word.lower())
                if w_ext in VALID_EXTENSIONS:
                    found_filename = clean_word
                    break
            if found_filename: break

            # 4. RapidFuzz Fallback: If the line contains common filename markers 
            # like "###", "File:", "Path:", check similarity.
            markers = ["###", "File:", "Filename:", "Update:", "Patching:"]
            res = process.extractOne(clean_line, markers, scorer=fuzz.PartialRatio)
            if res and res[1] > 80:
                # Try to extract the most 'file-like' token from this line
                potential_names = re.findall(r'[a-zA-Z0-9_\-\/]+\.[a-z]{2,4}', clean_line)
                if potential_names:
                    found_filename = potential_names[0]
                    break

        if found_filename:
            extracted_files.append((found_filename, content))
        else:
            extracted_files.append((preferred_filename, content))

    return extracted_files

def extract_code_blocks(text: str) -> List[str]:
    """Simple extractor that ignores filename association."""
    pattern = r"```(?:\w+)?\s*\n(.*?)\n```"
    return re.findall(pattern, text, re.DOTALL)
