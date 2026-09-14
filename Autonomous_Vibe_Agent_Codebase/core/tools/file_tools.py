"""
File manipulation tools: view_file, write_file, replace_file_content.
Includes smart path resolution and whitespace/quote normalization.
"""

import difflib
import os
from pathlib import Path
from typing import Any, Dict, Optional
from core.tools.base import Tool


def resolve_path(workspace_dir: str, file_path: Any) -> Path:
    """Resolve file path relative to workspace, stripping quotes, backticks, and whitespace."""
    if not file_path:
        return Path(workspace_dir)

    cleaned = str(file_path).strip().strip("\"'`").strip()
    # Normalize Windows backslashes / slashes
    cleaned = cleaned.replace("\\", "/")
    p = Path(cleaned)

    if not p.is_absolute():
        p = Path(workspace_dir) / p

    return p.resolve()


def find_file_in_workspace(workspace_dir: str, filename: str) -> Optional[Path]:
    """Search for a single file by name anywhere in workspace as a fuzzy fallback."""
    clean_name = Path(filename).name.strip("\"'`").strip()
    if not clean_name:
        return None

    root = Path(workspace_dir)
    matches = []
    ignored = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignored]
        if clean_name in filenames:
            matches.append(Path(dirpath) / clean_name)

    if len(matches) == 1:
        return matches[0]
    return None


def generate_diff(old_text: str, new_text: str, file_name: str) -> str:
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{file_name}",
        tofile=f"b/{file_name}",
        lineterm=""
    )
    return "".join(diff)


class ViewFileTool(Tool):
    name = "view_file"
    description = (
        "View the contents of a text file with 1-indexed line numbers. "
        "Optionally specify start_line and end_line to inspect a specific slice of the file."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to view (relative to workspace, e.g. 'main.py' or 'src/utils.py')."
            },
            "start_line": {
                "type": "integer",
                "description": "Optional 1-indexed start line number."
            },
            "end_line": {
                "type": "integer",
                "description": "Optional 1-indexed end line number."
            }
        },
        "required": ["file_path"]
    }

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir

    def execute(
        self,
        file_path: Optional[str] = None,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        **kwargs
    ) -> str:
        # Parameter aliases
        raw_path = file_path or kwargs.get("path") or kwargs.get("filepath") or kwargs.get("file") or ""
        if not raw_path or not str(raw_path).strip():
            return "Error: Missing 'file_path' argument."

        start_val = start_line if start_line is not None else kwargs.get("start")
        end_val = end_line if end_line is not None else kwargs.get("end")

        target = resolve_path(self.workspace_dir, raw_path)
        if not target.exists():
            # Try fuzzy fallback in workspace
            fallback = find_file_in_workspace(self.workspace_dir, str(raw_path))
            if fallback and fallback.exists():
                target = fallback
            else:
                return f"Error: File not found at '{raw_path}' (searched workspace '{self.workspace_dir}')"

        if target.is_dir():
            return f"Error: '{target}' is a directory, not a file. Use find_files instead."

        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            if total_lines == 0:
                return f"[File '{target.name}' is empty (0 lines)]"

            try:
                s = 1 if start_val is None or int(start_val) < 1 else int(start_val)
            except Exception:
                s = 1
            try:
                e = total_lines if end_val is None or int(end_val) > total_lines else int(end_val)
            except Exception:
                e = total_lines

            if s > total_lines:
                return f"Error: start_line {s} exceeds total lines ({total_lines}) in file."

            selected_lines = lines[s - 1:e]
            rel_path = target.relative_to(Path(self.workspace_dir)).as_posix() if Path(self.workspace_dir) in target.parents or target == Path(self.workspace_dir) else target.name
            output = [f"File: {rel_path} (Lines {s}-{e} of {total_lines})"]
            for idx, line in enumerate(selected_lines, start=s):
                output.append(f"{idx:5d} | {line.rstrip()}")

            return "\n".join(output)
        except Exception as ex:
            return f"Error reading file '{target}': {str(ex)}"


class WriteFileTool(Tool):
    name = "write_file"
    description = (
        "Create a new file or completely overwrite an existing file in the local project workspace. "
        "Parent directories will be created automatically."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file relative to the project workspace (e.g. 'app.py' or 'models/user.py')."
            },
            "content": {
                "type": "string",
                "description": "The full text content to write into the file."
            },
            "overwrite": {
                "type": "boolean",
                "description": "Set to true to overwrite existing files (default: true)."
            }
        },
        "required": ["file_path", "content"]
    }

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir

    def execute(
        self,
        file_path: Optional[str] = None,
        content: Optional[str] = None,
        overwrite: bool = True,
        **kwargs
    ) -> str:
        raw_path = file_path or kwargs.get("path") or kwargs.get("filepath") or kwargs.get("file") or ""
        raw_content = content if content is not None else kwargs.get("text", kwargs.get("code", kwargs.get("raw", "")))

        if not raw_path or not str(raw_path).strip():
            return "Error: Missing 'file_path' argument."

        target = resolve_path(self.workspace_dir, raw_path)
        if target.exists() and not overwrite:
            return f"Error: File '{target.name}' already exists and overwrite is set to False."

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(str(raw_content))
            line_count = len(str(raw_content).splitlines())
            rel_name = target.name
            try:
                rel_name = target.relative_to(Path(self.workspace_dir)).as_posix()
            except Exception:
                pass
            return f"Successfully wrote {line_count} lines to '{rel_name}'"
        except Exception as ex:
            return f"Error writing file '{target}': {str(ex)}"


class ReplaceFileContentTool(Tool):
    name = "replace_file_content"
    description = (
        "Replace a specific contiguous block of text within a file in the local project workspace. "
        "The target_content must match existing text in the file. "
        "This is much faster and token-efficient than rewriting the entire file."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to modify relative to workspace (e.g. 'main.py')."
            },
            "target_content": {
                "type": "string",
                "description": "The exact substring/block of code to replace."
            },
            "replacement_content": {
                "type": "string",
                "description": "The new content that replaces target_content."
            }
        },
        "required": ["file_path", "target_content", "replacement_content"]
    }

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir

    def execute(
        self,
        file_path: Optional[str] = None,
        target_content: Optional[str] = None,
        replacement_content: Optional[str] = None,
        **kwargs
    ) -> str:
        raw_path = file_path or kwargs.get("path") or kwargs.get("filepath") or kwargs.get("file") or ""
        raw_target = target_content if target_content is not None else kwargs.get("search", kwargs.get("old_str", kwargs.get("old_content", kwargs.get("search_block", ""))))
        raw_replacement = replacement_content if replacement_content is not None else kwargs.get("replace", kwargs.get("new_str", kwargs.get("new_content", kwargs.get("replace_block", ""))))

        if not raw_path or not str(raw_path).strip():
            return "Error: Missing 'file_path' argument."

        target = resolve_path(self.workspace_dir, raw_path)
        if not target.exists():
            # Try fuzzy fallback
            fallback = find_file_in_workspace(self.workspace_dir, str(raw_path))
            if fallback and fallback.exists():
                target = fallback
            else:
                return f"Error: File not found at '{raw_path}' in workspace '{self.workspace_dir}'"

        try:
            with open(target, "r", encoding="utf-8") as f:
                original_text = f.read()

            target_str = str(raw_target)
            replace_str = str(raw_replacement)

            norm_target = target_str.replace("\r\n", "\n")
            norm_original = original_text.replace("\r\n", "\n")
            norm_replacement = replace_str.replace("\r\n", "\n")

            match_count = norm_original.count(norm_target)
            if match_count == 0:
                stripped_target = norm_target.strip()
                if stripped_target and stripped_target in norm_original:
                    norm_target = stripped_target
                    match_count = norm_original.count(norm_target)
                else:
                    return (
                        f"Error: target_content not found in '{target.name}'. "
                        "Ensure target_content matches lines in the file exactly."
                    )

            if match_count > 1:
                return (
                    f"Error: target_content matched {match_count} locations in '{target.name}'. "
                    "Please include more surrounding context in target_content to make it unique."
                )

            new_text = norm_original.replace(norm_target, norm_replacement, 1)

            if "\r\n" in original_text:
                new_text = new_text.replace("\n", "\r\n")

            with open(target, "w", encoding="utf-8") as f:
                f.write(new_text)

            diff = generate_diff(original_text, new_text, target.name)
            return f"Successfully updated '{target.name}'.\n\nDiff:\n{diff}"

        except Exception as ex:
            return f"Error replacing content in '{target}': {str(ex)}"

