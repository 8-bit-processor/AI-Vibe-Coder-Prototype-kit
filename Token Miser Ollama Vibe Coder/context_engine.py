"""
The Intelligence Layer: Scans project structure and provides filtered context.

ContextEngine is responsible for building a technical map of the repository,
including symbol definitions (classes, functions), import relationships, and
linting violations. It provides 'smart' context filtering to ensure the LLM
receives relevant information without exceeding token limits.
"""

import os
import ast
import re
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Set, Tuple
from dependency_manager import DependencyManager

class ContextEngine:
    """
    Scans the project and builds a deep map of modules and symbols.

    Provides raw data (Symbol maps, dependency graphs, lint results) to the 
    ExecutionEngine and LLM. It focuses on extraction and filtering rather 
    than management logic.

    Attributes:
        project_root: The root directory of the project.
        module_map: Dictionary mapping filenames to their extracted metadata.
        lint_reports: Dictionary mapping filenames to lists of Ruff violations.
        viewed_files: Track which files have been processed in the current cycle.
    """

    def __init__(self, project_root: Path, logger_func):
        """
        Initializes the context engine.

        Args:
            project_root: Path to the project.
            logger_func: Logging callback.
        """
        self.project_root = project_root
        self.logger_func = logger_func
        self.module_map: Dict[str, Dict] = {}
        self.lint_reports: Dict[str, List[str]] = {}
        self.dep_manager = DependencyManager(project_root, logger_func)
        self._last_scan_time = 0
        self.viewed_files: Set[str] = set()
        self.logger_func("Context Engine initialized.")

    def get_viewed_files(self, reset: bool = True) -> List[str]:
        """
        Returns the list of files processed since the last reset.

        Args:
            reset: If True, clears the viewed_files set after returning.

        Returns:
            Sorted list of file paths.
        """
        files = sorted(list(self.viewed_files))
        if reset:
            self.viewed_files = set()
        return files

    def run_linter(self):
        """
        Detects code smells via Ruff and populates lint_reports.

        Calls the Ruff CLI in JSON mode and parses violations into a 
        human-readable format associated with each file.
        """
        self.lint_reports = {}
        try:
            # Run Ruff check on the whole project
            result = subprocess.run(
                ["python", "-m", "ruff", "check", str(self.project_root), "--output-format", "json", "--quiet"],
                capture_output=True, text=True
            )
            if result.stdout:
                violations = json.loads(result.stdout)
                for v in violations:
                    rel_path = os.path.relpath(v["filename"], self.project_root)
                    if rel_path not in self.lint_reports:
                        self.lint_reports[rel_path] = []
                    msg = f"[{v['code']}] {v['message']} (Line {v['location']['row']})"
                    self.lint_reports[rel_path].append(msg)
        except Exception as e:
            self.logger_func(f"Linter error: {e}", "WARNING")

    def scan_project(self, force: bool = False):
        """
        Builds a comprehensive map of modules, symbols, and relationships.

        Iterates through all .py files, parses them into Abstract Syntax Trees (AST),
        and extracts classes, functions, and imports. It also triggers the 
        DependencyManager to update the project graph.

        Args:
            force: If True, bypasses the timestamp check and rescans everything.
        """
        py_files = list(self.project_root.rglob("*.py"))
        latest_mtime = 0
        # Optimization: Only scan if files have changed since the last run
        for f in py_files:
            rel = os.path.relpath(f, self.project_root)
            if ".venv" in rel or "__pycache__" in rel:
                continue
            mtime = os.path.getmtime(f)
            if mtime > latest_mtime:
                latest_mtime = mtime
        
        if not force and latest_mtime <= self._last_scan_time:
            return

        self.module_map = {}
        self.dep_manager.reset()
        self.run_linter()
        self.dep_manager.map_local_modules(py_files)

        for py_file in py_files:
            rel_path = os.path.relpath(py_file, self.project_root)
            # Skip noise
            if ".venv" in rel_path or "__pycache__" in rel_path:
                continue
                
            self.viewed_files.add(rel_path)
            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content)
                module_info = {
                    "docstring": ast.get_docstring(tree) or "",
                    "classes": {},
                    "functions": {},
                    "imports": [],
                    "path": rel_path,
                    "complexity_score": 0
                }
                # Traverse AST to find symbols
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.ClassDef):
                        methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                        module_info["classes"][node.name] = {"methods": methods, "docstring": ast.get_docstring(node)}
                    elif isinstance(node, ast.FunctionDef):
                        module_info["functions"][node.name] = {"docstring": ast.get_docstring(node)}
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        if isinstance(node, ast.Import):
                            for n in node.names:
                                module_info["imports"].append(n.name)
                        else:
                            module_info["imports"].append(node.module or "")
                
                # Simple complexity metric based on symbol count
                module_info["complexity_score"] = len(module_info["classes"]) + len(module_info["functions"])
                self.module_map[rel_path] = module_info
                
                # Map dependencies based on imports
                for imp in module_info["imports"]:
                    resolved = self.dep_manager.resolve_import(imp, rel_path)
                    if resolved:
                        self.dep_manager.add_dependency(rel_path, resolved)
            except Exception as e:
                self.logger_func(f"Scan error {rel_path}: {e}", "WARNING")
        
        self._last_scan_time = latest_mtime or 1

    def get_architectural_summary(self) -> str:
        """
        Returns a high-level summary of the project's purpose and layout.

        Uses module docstrings to provide a quick overview of what each file does.

        Returns:
            A formatted summary string.
        """
        self.scan_project()
        summary = "### PROJECT ARCHITECTURAL SUMMARY ###\n"
        for rel_path, info in sorted(self.module_map.items()):
            self.viewed_files.add(rel_path)
            purpose = info.get("docstring", "").split("\n")[0]
            summary += f"- {rel_path}: {purpose}\n"
        return summary

    def get_symbol_map(self) -> str:
        """
        Returns a formatted map of all public symbols in the project.

        Returns:
            A string containing files, classes, and functions.
        """
        self.scan_project()
        report = "### PROJECT SYMBOL MAP ###\n"
        for rel_path, info in sorted(self.module_map.items()):
            self.viewed_files.add(rel_path)
            public_classes = [c for c in info["classes"] if not c.startswith("_")]
            public_funcs = [f for f in info["functions"] if not f.startswith("_")]
            if not public_classes and not public_funcs:
                continue
            report += f"\nFILE: {rel_path}\n"
            for cls in public_classes:
                methods = [m for m in info["classes"][cls]["methods"] if not m.startswith("_")]
                report += f"  - Class: {cls} (Methods: {', '.join(methods)})\n"
            for func in public_funcs:
                report += f"  - Function: {func}\n"
        return report

    def prune_code(self, code: str) -> str:
        """
        Removes docstrings and comments from Python code to save tokens.

        This uses the AST to surgically remove docstring nodes and regex to
        strip inline comments. Useful for secondary context files.

        Args:
            code: Raw source code.

        Returns:
            Minified source code.
        """
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                # Remove docstrings by popping the first expression if it's a string literal
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                    if (node.body and isinstance(node.body[0], ast.Expr) and
                        isinstance(node.body[0].value, ast.Constant) and 
                        isinstance(node.body[0].value.value, str)):
                        node.body.pop(0)
            
            # Convert back to source (requires python 3.9+)
            pruned = ast.unparse(tree)
            # Remove line comments using regex
            pruned = re.sub(r'#.*$', '', pruned, flags=re.MULTILINE)
            # Clean up extra newlines for maximum token efficiency
            pruned = re.sub(r'\n\s*\n', '\n', pruned)
            return pruned.strip()
        except Exception:
            return code # Fallback to original if AST parsing fails

    def get_smart_context(self, prompt: str, target_file: str = "None", max_size: int = 100000, prune: bool = True) -> Tuple[str, str]:
        """
        Filters and ranks project files based on relevance to the prompt.

        Algorithm:
        1. Keyword scoring: Matches keywords from prompt against file paths and symbols.
        2. Graph scoring: Propagates scores to dependencies (if A is relevant, B imported by A is likely relevant).
        3. Sorting: Orders files by score.
        4. Budgeting: Adds files to context until max_size is reached.
        5. Pruning: Optionally minifies non-target files to fit more context.

        Args:
            prompt: User task description.
            target_file: The file currently being worked on (gets top priority).
            max_size: Maximum character count for the context block.
            prune: Whether to minify code in the context.

        Returns:
            A tuple of (full_context_text, summary_report).
        """
        self.scan_project()
        keywords = set(re.findall(r'\w+', prompt.lower()))
        scores: Dict[str, float] = {}
        
        for rel_path, info in self.module_map.items():
            score = 0.0
            # Target file is always priority 1
            if target_file and rel_path == target_file:
                score += 100.0
            
            path_lower = rel_path.lower()
            for kw in keywords:
                if kw in path_lower:
                    score += 10.0
            
            # Match against classes and functions
            symbols = list(info["classes"].keys()) + list(info["functions"].keys())
            for sym in symbols:
                sym_lower = sym.lower()
                for kw in keywords:
                    if kw in sym_lower:
                        score += 5.0
            scores[rel_path] = score

        # Propagate scores through the dependency graph
        final_scores = scores.copy()
        for rel_path, score in scores.items():
            if score > 5.0:
                for dep in self.dep_manager.dependency_graph.get(rel_path, []):
                    if dep in final_scores:
                        final_scores[dep] += score * 0.5 # Dependencies get half the score boost

        # Sort files by their relevance score
        sorted_modules = sorted(final_scores.keys(), key=lambda x: final_scores[x], reverse=True)
        context_text = "### SMART PROJECT CONTEXT ###\n"
        
        # ERROR PRIORITIZATION: If a recent runtime or verification error exists, 
        # inject it at the VERY TOP of the context. This forces the LLM to address 
        # the immediate failure before looking at general project code.
        if hasattr(self, 'session_orchestrator') and self.session_orchestrator.last_run_error:
            context_text += f"\n[RECENT CRITICAL ERROR]\n{self.session_orchestrator.last_run_error}\n"
        
        summary_text = "Context Loaded:\n"
        current_size = 0
        
        for rel_path in sorted_modules:
            file_path = self.project_root / rel_path
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                is_target = target_file and rel_path == target_file
                
                # Prune non-essential files to save tokens
                if not is_target and prune and rel_path.endswith(".py"):
                    content = self.prune_code(content)
                
                # Check token/character budget
                if current_size + len(content) > max_size:
                    break
                
                self.viewed_files.add(rel_path)
                context_text += f"\n--- {rel_path} ---\n{content}\n"
                summary_text += f"- {rel_path} ({final_scores.get(rel_path, 0):.1f})\n"
                current_size += len(content)
            except Exception:
                continue

        return context_text, summary_text
