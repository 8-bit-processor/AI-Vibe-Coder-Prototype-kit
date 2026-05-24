"""
Analyzes and maps relationships between project modules.

The DependencyManager tracks how files import one another and identifies 
external package dependencies. It builds a directed graph which the ContextEngine 
uses to propagate relevance scores during context gathering.
"""

import os
from pathlib import Path
from typing import List, Dict, Set, Optional

class DependencyManager:
    """
    Manages the project's dependency graph and handles import resolution.

    Attributes:
        project_root: The root path of the project.
        dependency_graph: Maps a file to the set of files it imports.
        reverse_dependency_graph: Maps a file to the set of files that import it.
        module_to_file: Mapping of dotted module names (e.g., 'utils.db') to file paths.
        external_dependencies: Set of top-level external package names discovered.
    """

    def __init__(self, project_root: Path, logger_func):
        """
        Initializes the dependency manager.

        Args:
            project_root: Absolute path to project root.
            logger_func: Logging callback.
        """
        self.project_root = project_root
        self.logger_func = logger_func
        self.dependency_graph: Dict[str, Set[str]] = {}
        self.reverse_dependency_graph: Dict[str, Set[str]] = {}
        self.module_to_file: Dict[str, str] = {}
        self.external_dependencies: Set[str] = set()

    def reset(self):
        """Clears all internal graphs and maps to prepare for a fresh scan."""
        self.dependency_graph = {}
        self.reverse_dependency_graph = {}
        self.module_to_file = {}
        self.external_dependencies = set()

    def map_local_modules(self, py_files: List[Path]):
        """
        Creates a map of Python module names to their relative file paths.

        Converts filesystem paths (e.g., 'core/utils.py') into Python 
        module dots (e.g., 'core.utils') for lookups during import resolution.

        Args:
            py_files: List of absolute Paths to all .py files in the project.
        """
        for f in py_files:
            rel = os.path.relpath(f, self.project_root)
            # Skip environment and cache folders
            if ".venv" in rel or "__pycache__" in rel:
                continue
            # Normalize separators and remove extension
            mod_name = rel.replace(os.sep, ".").replace(".py", "").strip(".")
            self.module_to_file[mod_name] = rel

    def resolve_import(self, imp_name: str, current_file_rel: str) -> Optional[str]:
        """
        Attempts to resolve an import name to a local file path.

        If the import matches a local module, it returns the relative path to 
        that module. Otherwise, it tracks the base package as an external 
        dependency.

        Args:
            imp_name: The raw import string (e.g., 'os', 'my_project.core').
            current_file_rel: Relative path of the file containing the import.

        Returns:
            The relative path to the local module, or None if external.
        """
        # 1. Check for exact local match or sub-module match
        for mod_name, mod_file in self.module_to_file.items():
            if imp_name == mod_name or imp_name.startswith(mod_name + "."):
                if mod_file != current_file_rel:
                    return mod_file
        
        # 2. If not found locally, treat as external and track the base package
        base_pkg = imp_name.split('.')[0]
        self.external_dependencies.add(base_pkg)
        return None

    def add_dependency(self, source_file_rel: str, target_file_rel: str):
        """
        Adds a directed edge to the dependency graphs.

        Args:
            source_file_rel: The file that is doing the importing.
            target_file_rel: The file being imported.
        """
        if source_file_rel not in self.dependency_graph:
            self.dependency_graph[source_file_rel] = set()
        self.dependency_graph[source_file_rel].add(target_file_rel)

        # Build reverse graph for 'who imports me' queries
        if target_file_rel not in self.reverse_dependency_graph:
            self.reverse_dependency_graph[target_file_rel] = set()
        self.reverse_dependency_graph[target_file_rel].add(source_file_rel)

    def get_external_packages(self) -> List[str]:
        """
        Returns a sorted list of unique external packages imported.

        Returns:
            Alphabetical list of package names (e.g., ['requests', 'rich']).
        """
        return sorted(list(self.external_dependencies))
