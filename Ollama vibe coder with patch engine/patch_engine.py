import re
import difflib
from rapidfuzz import fuzz, process
from code_validator import validate_code

def normalize(text: str) -> str:
    """
    Normalizes a block of code for comparison.
    Strips leading/trailing whitespace from each line and removes empty lines.
    This helps match code even if the LLM changes blank line spacing.
    """
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    return "\n".join(lines)

def get_indentation(text: str) -> str:
    """
    Detects the leading indentation of the first non-empty line in a block.
    Returns the exact string of spaces or tabs used.
    """
    lines = text.splitlines()
    for line in lines:
        if line.strip():
            match = re.match(r'^(\s*)', line)
            return match.group(1) if match else ""
    return ""

def adjust_indentation(target_indent: str, replace_text: str) -> str:
    """
    Re-indents a block of replacement code to match the target file's indentation.
    It detects the LLM's chosen indentation and shifts it to match 'target_indent'.
    """
    original_indent = get_indentation(replace_text)
    if original_indent == target_indent:
        return replace_text
    
    lines = replace_text.splitlines()
    adjusted_lines = []
    for line in lines:
        if line.startswith(original_indent):
            # Replace the old indent with the new one
            adjusted_lines.append(target_indent + line[len(original_indent):])
        elif not line.strip():
            # Keep blank lines as-is
            adjusted_lines.append("")
        else:
            # For lines with less indentation than the first line, keep them relative
            adjusted_lines.append(line)
    return "\n".join(adjusted_lines)

def try_exact_match(file_content: str, search_text: str, replace_text: str) -> str | None:
    """
    Tier 1: Performs a literal string replacement.
    If search_text is found exactly, it is replaced with an auto-indented version of replace_text.
    """
    if search_text in file_content:
        target_indent = get_indentation(search_text)
        adjusted_replace = adjust_indentation(target_indent, replace_text)
        return file_content.replace(search_text, adjusted_replace)
    return None

def try_normalized_match(file_content: str, search_text: str, replace_text: str) -> str | None:
    """
    Tier 2: Matches code blocks by ignoring whitespace and blank line differences.
    Iterates through the file using a sliding window to find a normalized match.
    """
    norm_search = normalize(search_text)
    file_lines = file_content.splitlines()
    search_line_count = len(search_text.splitlines())
    
    for i in range(len(file_lines) - search_line_count + 1):
        window = file_lines[i:i+search_line_count]
        if normalize("\n".join(window)) == norm_search:
            target_indent = get_indentation("\n".join(window))
            adjusted_replace = adjust_indentation(target_indent, replace_text)
            return "\n".join(file_lines[:i] + [adjusted_replace] + file_lines[i+search_line_count:])
    return None

def try_context_match(file_content: str, search_text: str, replace_text: str) -> str | None:
    """
    Tier 3: Anchors the patch on the first line of the search block (e.g., function header).
    Useful when the LLM gets the function body slightly wrong but the header is unique.
    """
    lines = search_text.splitlines()
    if not lines: return None
    anchor = lines[0].strip()
    
    file_lines = file_content.splitlines()
    for i, line in enumerate(file_lines):
        if anchor in line:
            search_line_count = len(lines)
            target_indent = get_indentation(file_lines[i])
            adjusted_replace = adjust_indentation(target_indent, replace_text)
            return "\n".join(file_lines[:i] + [adjusted_replace] + file_lines[i+search_line_count:])
    return None

def try_fuzzy_match(file_content: str, search_text: str, replace_text: str) -> str | None:
    """
    Tier 4: Uses Levenshtein distance to find the most similar block of code.
    Accepts matches with >85% similarity. Essential for resilient 'vibe coding'.
    """
    file_lines = file_content.splitlines()
    search_lines = search_text.splitlines()
    search_len = len(search_lines)
    
    if search_len == 0: return None
    
    best_ratio = 0
    best_idx = -1
    
    # Slide a window across the file to find the best fuzzy fit
    for i in range(len(file_lines) - search_len + 1):
        window = "\n".join(file_lines[i:i+search_len])
        ratio = fuzz.ratio(window, search_text)
        if ratio > best_ratio:
            best_ratio = ratio
            best_idx = i
            
    if best_ratio > 85:
        target_indent = get_indentation(file_lines[best_idx])
        adjusted_replace = adjust_indentation(target_indent, replace_text)
        return "\n".join(file_lines[:best_idx] + [adjusted_replace] + file_lines[best_idx+search_len:])
    
    return None

def apply_patch(file_path: str, patch_content: str) -> tuple[bool, str]:
    """
    The main orchestration engine for surgical code repairs.
    
    Features:
    1. Regex-based parsing of multiple ### SEARCH ###/### REPLACE ### blocks.
    2. Conflict detection to prevent overlapping modifications.
    3. 4-tier matching strategy (Exact -> Normalized -> Contextual -> Fuzzy).
    4. Automatic indentation alignment to match local coding style.
    5. Post-patch syntax validation using AST.
    
    Returns: (success_boolean, status_message)
    """
    # Find all pairs of SEARCH and REPLACE blocks
    pattern = r'### SEARCH ###\s*\n(.*?)\n\s*### REPLACE ###\s*\n(.*?)(?=\n\s*### SEARCH ###|\Z)'
    matches = re.findall(pattern, patch_content, re.DOTALL)

    if not matches:
        return False, "Invalid patch format. No SEARCH/REPLACE blocks found."

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except Exception as e:
        return False, f"Failed to read target file: {str(e)}"

    new_content = original_content
    applied_count = 0
    
    for search_text, replace_text in matches:
        search_text = search_text.strip()
        replace_text = replace_text.strip()
        
        # Conflict Detection: Prevent corrupting the file if multiple patches hit the same spot
        if search_text not in new_content and search_text in original_content:
             return False, "Critical Conflict: Multiple blocks in this patch are targeting the same code region."

        applied_this_block = False
        # Execute the 4-tier strategy
        for tier_name, func in [
            ("Exact Match", try_exact_match),
            ("Normalized Match", try_normalized_match),
            ("Contextual Match", try_context_match),
            ("Fuzzy Match", try_fuzzy_match)
        ]:
            result = func(new_content, search_text, replace_text)
            if result:
                new_content = result
                applied_this_block = True
                applied_count += 1
                break
        
        if not applied_this_block:
            # Fallback: Provide a diff to help the user resolve the failure manually
            diff = list(difflib.unified_diff(
                search_text.splitlines(), 
                replace_text.splitlines(), 
                fromfile='Original (Search)', 
                tofile='Proposed (Replace)'
            ))
            return False, f"Tier matching failed for a block. Diff for manual review:\n" + "\n".join(diff)

    # Safety Guard: Ensure the patch hasn't introduced syntax errors
    is_valid, error = validate_code(new_content)
    if not is_valid:
        return False, f"Surgical patch aborted! The resulting code has syntax errors: {error}"

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
    except Exception as e:
        return False, f"Failed to write patch to disk: {str(e)}"
        
    return True, f"Successfully applied {applied_count} patch block(s) with syntax validation."
