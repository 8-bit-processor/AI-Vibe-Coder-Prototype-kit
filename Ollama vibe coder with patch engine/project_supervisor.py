import os
import ast
import re
from pathlib import Path
from typing import List, Dict, Set

class ProjectSupervisor:
    def __init__(self, project_root: Path, logger_func):
        self.project_root = project_root
        self.logger_func = logger_func
        self.module_map: Dict[str, Dict] = {}
        self.dependency_graph: Dict[str, Set[str]] = {}
        self.logger_func("Project Supervisor initialized.")

    def scan_project(self):
        """
        Scans the project to build a map of modules and their relationships.
        """
        self.module_map = {}
        self.dependency_graph = {}
        
        py_files = list(self.project_root.rglob("*.py"))
        for py_file in py_files:
            rel_path = os.path.relpath(py_file, self.project_root)
            if ".venv" in rel_path or "__pycache__" in rel_path:
                continue
                
            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content)
                
                module_info = {
                    "classes": [],
                    "functions": [],
                    "imports": [],
                    "path": rel_path
                }
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        module_info["classes"].append(node.name)
                    elif isinstance(node, ast.FunctionDef):
                        module_info["functions"].append(node.name)
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        if isinstance(node, ast.Import):
                            for n in node.names:
                                module_info["imports"].append(n.name)
                        else:
                            module_info["imports"].append(node.module or "")
                
                self.module_map[rel_path] = module_info
                
                # Update dependency graph
                self.dependency_graph[rel_path] = set()
                for imp in module_info["imports"]:
                    # Try to resolve local imports
                    for other_file in py_files:
                        other_rel = os.path.relpath(other_file, self.project_root)
                        other_mod = other_rel.replace(os.sep, ".").replace(".py", "")
                        if imp and (imp == other_mod or imp.startswith(other_mod + ".")):
                            self.dependency_graph[rel_path].add(other_rel)
                            
            except Exception as e:
                self.logger_func(f"Supervisor scan error on {rel_path}: {e}", "WARNING")

    def audit_architecture(self) -> List[str]:
        """
        Analyzes the project structure for coordination issues.
        """
        concerns = []
        
        # 1. Check for circular dependencies
        for start_node in self.dependency_graph:
            visited = set()
            stack = [(start_node, [start_node])]
            while stack:
                node, path = stack.pop()
                if node in self.dependency_graph:
                    for neighbor in self.dependency_graph[node]:
                        if neighbor == start_node:
                            concerns.append(f"CRITICAL: Circular dependency detected: {' -> '.join(path)} -> {neighbor}")
                        elif neighbor not in visited:
                            visited.add(neighbor)
                            stack.append((neighbor, path + [neighbor]))

        # 2. Check for potentially redundant functionality
        all_funcs = {}
        for mod, info in self.module_map.items():
            for func in info["functions"]:
                if func not in all_funcs:
                    all_funcs[func] = []
                all_funcs[func].append(mod)
        
        for func, mods in all_funcs.items():
            if len(mods) > 1 and not func.startswith("_"):
                concerns.append(f"ADVISORY: Function name '{func}' is duplicated across modules: {', '.join(mods)}. Ensure logic is not redundant.")

        # 3. Check for "God Modules" (too many responsibilities)
        for mod, info in self.module_map.items():
            if len(info["classes"]) + len(info["functions"]) > 15:
                concerns.append(f"ADVISORY: Module '{mod}' appears bloated. Consider refactoring into smaller, specialized modules.")

        return concerns

    def get_supervisor_report(self) -> str:
        """
        Generates a summary report for the LLM.
        """
        self.scan_project()
        concerns = self.audit_architecture()
        
        report = "### PROJECT SUPERVISOR ARCHITECTURAL REPORT ###\n"
        if not concerns:
            report += "STATUS: Project architecture is healthy and logically coordinated.\n"
        else:
            report += "STATUS: ARCHITECTURAL ALERTS DETECTED\n"
            for concern in concerns:
                report += f"- {concern}\n"
        
        report += "\nSUPERVISOR CAPABILITIES:\n"
        report += "- I can create new files and modules to maintain project structure.\n"
        report += "- I can validate that new code adheres to the project's architectural standards.\n"
        report += "- I can detect redundant logic and circular dependencies.\n"
        
        report += "\nINSTRUCTION TO CODER: When proposing changes, ensure you are not just fixing bugs but also improving the overall architecture. If a module is getting too large, ask me to help you split it into smaller, specialized files."
        return report

    def create_file(self, filename: str, content: str):
        """
        Delegated method for file creation (orchestrated via PatchCoordinator in main.py).
        Included here for architectural completeness and future expansion.
        """
        self.logger_func(f"Supervisor approved creation of: {filename}")
        # In the current architecture, main.py handles the actual writing via PatchCoordinator.
        # This method serves as a hook for the Supervisor to 'approve' or 'log' the action.
        pass
