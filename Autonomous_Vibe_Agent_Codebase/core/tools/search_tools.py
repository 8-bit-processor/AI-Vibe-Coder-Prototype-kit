"""
Codebase search tools: grep_search and find_files.
"""

import fnmatch
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from core.tools.base import Tool

IGNORED_DIRS = {
    ".git", ".svn", ".hg", "__pycache__", "node_modules",
    ".venv", "venv", "env", ".idea", ".vscode", "dist", "build"
}


class GrepSearchTool(Tool):
    name = "grep_search"
    description = (
        "Search for text or regular expressions across files in the workspace. "
        "Returns matched file paths, line numbers, and snippets."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The string or regex pattern to search for."
            },
            "path": {
                "type": "string",
                "description": "Optional subdirectory or file to restrict search to."
            },
            "is_regex": {
                "type": "boolean",
                "description": "Whether query should be treated as regex (default: false)."
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum matching lines to return (default: 50)."
            }
        },
        "required": ["query"]
    }

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir

    def execute(
        self,
        query: Optional[str] = None,
        path: Optional[str] = None,
        is_regex: bool = False,
        max_results: int = 50,
        **kwargs
    ) -> str:
        raw_query = query if query is not None else kwargs.get("pattern", kwargs.get("regex", kwargs.get("search_term", kwargs.get("text", ""))))
        query_str = str(raw_query).strip() if raw_query is not None else ""
        if not query_str:
            return "Error: Missing 'query' argument."

        raw_path = path if path is not None else kwargs.get("sub_dir", kwargs.get("dir", kwargs.get("directory", kwargs.get("target_path"))))
        root = Path(self.workspace_dir)
        if raw_path:
            target_path = root / str(raw_path) if not Path(str(raw_path)).is_absolute() else Path(str(raw_path))
        else:
            target_path = root

        if not target_path.exists():
            return f"Error: Search path '{target_path}' does not exist."

        try:
            pattern = re.compile(query_str if is_regex else re.escape(query_str), re.IGNORECASE)
        except re.error as e:
            return f"Error: Invalid regular expression '{query_str}': {str(e)}"

        try:
            max_r = int(max_results)
        except Exception:
            max_r = 50

        results = []
        files_to_search: List[Path] = []

        if target_path.is_file():
            files_to_search.append(target_path)
        else:
            for dirpath, dirnames, filenames in os.walk(target_path):
                dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
                for filename in filenames:
                    files_to_search.append(Path(dirpath) / filename)

        for file_p in files_to_search:
            if len(results) >= max_r:
                break
            try:
                with open(file_p, "r", encoding="utf-8", errors="replace") as f:
                    for line_num, line in enumerate(f, start=1):
                        if pattern.search(line):
                            rel_path = file_p.relative_to(root)
                            results.append(f"{rel_path.as_posix()}:{line_num}: {line.strip()}")
                            if len(results) >= max_r:
                                break
            except Exception:
                continue

        if not results:
            return f"No matches found for '{query_str}' in {target_path}."

        header = f"Found {len(results)} match(es)" + (f" (capped at {max_r}):" if len(results) >= max_r else ":")
        return header + "\n" + "\n".join(results)


class FindFilesTool(Tool):
    name = "find_files"
    description = (
        "Find files in the workspace matching a glob pattern (e.g. '*.py', 'test_*.js', 'config.*')."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match file names against (e.g. '*.py', '**/*.json')."
            },
            "sub_dir": {
                "type": "string",
                "description": "Optional subdirectory to restrict search to."
            }
        },
        "required": ["pattern"]
    }

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir

    def execute(self, pattern: Optional[str] = None, sub_dir: Optional[str] = None, **kwargs) -> str:
        raw_pattern = pattern if pattern is not None else kwargs.get("query", kwargs.get("name", kwargs.get("file_pattern", kwargs.get("glob", "*"))))
        pattern_str = str(raw_pattern).strip() if raw_pattern is not None else "*"

        raw_dir = sub_dir if sub_dir is not None else kwargs.get("path", kwargs.get("dir", kwargs.get("directory")))
        root = Path(self.workspace_dir)
        start_dir = root / str(raw_dir) if raw_dir else root

        if not start_dir.exists():
            return f"Error: Subdirectory '{start_dir}' does not exist."

        matches = []
        for dirpath, dirnames, filenames in os.walk(start_dir):
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
            for filename in filenames:
                full_p = Path(dirpath) / filename
                rel_p = full_p.relative_to(root)
                rel_posix = rel_p.as_posix()
                if fnmatch.fnmatch(filename, pattern_str) or fnmatch.fnmatch(rel_posix, pattern_str):
                    matches.append(rel_posix)

        if not matches:
            return f"No files matching pattern '{pattern_str}' found."

        return f"Found {len(matches)} file(s):\n" + "\n".join(matches)

