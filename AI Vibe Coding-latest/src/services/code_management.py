import json
from pathlib import Path
from typing import List
from src.services.base import BaseService

class CodeManagementServices(BaseService):
    """
    Service responsible for file-level operations and project indexing.

    Handles saving code, scanning project directories, searching file 
    contents, and maintaining a lightweight index of modules and their purposes.
    """
    def __init__(self, project_dir: Path, orchestrator=None):
        """
        Initializes the service and loads the project index.

        Args:
            project_dir (Path): The root directory of the project.
            orchestrator: The orchestrator instance.
        """
        super().__init__(orchestrator)
        self.project_dir = project_dir
        self.index_file = self.project_dir / ".project_index.json"
        self.index = self._load_index()

    def _load_index(self):
        """Loads the project index from a JSON file, or returns a default structure."""
        if self.index_file.exists():
            with open(self.index_file, 'r') as f:
                return json.load(f)
        return {"modules": {}}

    def _save_index(self):
        """Persists the current project index to a JSON file."""
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2)

    def register_module(self, filename: str, purpose: str):
        """
        Adds or updates a module in the project index.

        Args:
            filename (str): The name of the file.
            purpose (str): A brief description of the file's purpose.
        """
        self.index["modules"][filename] = {"purpose": purpose}
        self._save_index()
    
    def get_module_info(self, filename: str):
        """Retrieves indexing information for a specific file."""
        return self.index["modules"].get(filename)

    def save_code(self, filename: str, content: str, purpose: str = ""):
        """
        Writes code to a file and registers it in the project index.

        Args:
            filename (str): The name/path of the file to save.
            content (str): The source code content.
            purpose (str, optional): The purpose of the module.
        """
        file_path = self.project_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        self.register_module(filename, purpose)

    def delete_file(self, filename: str):
        """
        Deletes a file from the project and removes it from the index.

        Args:
            filename (str): The relative path to the file.
        """
        file_path = self.project_dir / filename
        if file_path.exists() and file_path.is_file():
            file_path.unlink()
            # Update Index
            if filename in self.index["modules"]:
                del self.index["modules"][filename]
                self._save_index()
            return True
        return False

    def rename_file(self, old_name: str, new_name: str):
        """
        Renames a file in the project and updates the index.

        Args:
            old_name (str): The current relative filename.
            new_name (str): The new relative filename.
        """
        old_path = self.project_dir / old_name
        new_path = self.project_dir / new_name
        
        if old_path.exists():
            new_path.parent.mkdir(parents=True, exist_ok=True)
            old_path.rename(new_path)
            
            # Update Index
            if old_name in self.index["modules"]:
                self.index["modules"][new_name] = self.index["modules"].pop(old_name)
                self._save_index()
            
            return True
        return False

    def get_build_dir(self) -> Path:
        """
        Determines the appropriate working directory for shell commands.

        It looks for a directory containing '.project_index.json', starting 
        at the root and checking immediate hidden subdirectories.

        Returns:
            Path: The detected build or project directory.
        """
        # 1. Check if the current project_dir has an index
        if (self.project_dir / ".project_index.json").exists():
            return self.project_dir
            
        # 2. Search for hidden subdirectories that might contain the index (build folders)
        for path in self.project_dir.iterdir():
            if path.is_dir() and path.name.startswith('.') and (path / ".project_index.json").exists():
                return path
                
        return self.project_dir

    def _should_skip(self, path: Path) -> bool:
        """
        Determines if a file or directory should be ignored during scans.

        Args:
            path (Path): The path to evaluate.

        Returns:
            bool: True if the path should be skipped, False otherwise.
        """
        # Common junk patterns to always skip
        skip_patterns = {'.git', '__pycache__', '.venv', '.pytest_cache', '.vscode', '.idea'}
        
        try:
            # Get parts relative to the project root
            relative_parts = path.relative_to(self.project_dir).parts
            
            for part in relative_parts:
                # Always skip common junk
                if part in skip_patterns:
                    return True
                # Skip hidden files/dirs EXCEPT for the project root subdirectory itself
                # (allowing things like .space invaders if that's where the code lives)
                if part.startswith('.') and part not in ['.', '..'] and part not in skip_patterns:
                    # If the user specifically targeted a hidden directory, don't hide its children
                    continue
            return False
        except Exception:
            return True

    def scan_project(self) -> str:
        """
        Scans the project and returns a concatenated summary of code files.

        Returns:
            str: A formatted string containing filenames and their content.
        """
        summary = []
        for file_path in self.project_dir.rglob('*'):
            if file_path.is_file() and not self._should_skip(file_path):
                if file_path.suffix in ['.py', '.md', '.txt', '.json']:
                    try:
                        content = file_path.read_text()
                        summary.append(f"--- File: {file_path.relative_to(self.project_dir)} ---\n{content}\n")
                    except Exception:
                        continue
        return "\n".join(summary)

    def list_files(self, sub_dir: str = ".") -> List[str]:
        """
        Lists non-ignored files in a directory.

        Args:
            sub_dir (str): The subdirectory to list (relative to project root).

        Returns:
            List[str]: A list of relative file paths.
        """
        target_dir = self.project_dir / sub_dir
        if not target_dir.exists():
            return []
        return [str(f.relative_to(self.project_dir)) for f in target_dir.iterdir() if not self._should_skip(f)]

    def get_tree(self) -> str:
        """
        Generates a visual tree representation of the project structure.
        Truncates venv contents to save token space.

        Returns:
            str: A formatted string showing the directory hierarchy.
        """
        tree = []
        for path in sorted(self.project_dir.rglob('*')):
            if self._should_skip(path):
                continue
            
            # Special handling for venv: show it, but skip children
            is_venv_child = False
            for part in path.relative_to(self.project_dir).parts:
                if part == 'venv':
                    if path.name != 'venv':
                        is_venv_child = True
                    break
            if is_venv_child:
                continue

            depth = len(path.relative_to(self.project_dir).parts) - 1
            if depth < 0: continue # Root itself
            indent = "  " * depth

            # Highlight files in the index (recently modified/registered)
            marker = "* " if path.name in self.index["modules"] else "- "
            tree.append(f"{indent}{'+ ' if path.is_dir() else marker}{path.name}")
        return "\n".join(tree)

    def grep(self, pattern: str) -> str:
        """
        Searches for a text pattern within all Python files in the project.

        Args:
            pattern (str): The string to search for.

        Returns:
            str: A formatted string of matches with line numbers.
        """
        results = []
        for file_path in self.project_dir.rglob('*.py'):
            if self._should_skip(file_path):
                continue
            try:
                content = file_path.read_text(errors='replace')
                for i, line in enumerate(content.splitlines()):
                    if pattern.lower() in line.lower():
                        results.append(f"{file_path.name}:{i+1}: {line.strip()}")
            except Exception:
                continue
        return "\n".join(results) if results else f"No matches found for '{pattern}'."


    def read_file(self, filename: str) -> str:
        """
        Reads the content of a file from the project.

        Args:
            filename (str): The relative path to the file.

        Returns:
            str: The file content, or an error message.
        """
        file_path = self.project_dir / filename
        if file_path.exists() and file_path.is_file():
            return file_path.read_text()
        return f"Error: File {filename} not found."

