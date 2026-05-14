import asyncio
import re
import datetime
import questionary
import os # Added for path operations
from pathlib import Path
from refactor_engine import determine_intent, build_system_prompt, get_diagnostic_prompt, get_rewrite_prompt
from code_validator import validate_code, check_blocking_code
from patch_engine import apply_patch
from llm.ollama_client import OllamaClient
from llm.openai_client import OpenAIClient
from cli import select_model, select_project_dir
from code_extractor import extract_code_blocks
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

class PatchCoordinator:
    def __init__(self, project_root: str, logger_func):
        self.project_root = Path(project_root)
        self.logger_func = logger_func
        self._saved_files = []
        self._conversation_history = []
        self._last_patch_result = None
        self._last_validation_results = []
        self._last_warnings = []
        self._current_working_file = None
        self._last_problematic_code = None
        self._original_project_purpose = None
        self.logger_func("PatchCoordinator initialized.")

    def add_to_conversation_history(self, role, content):
        self._conversation_history.append({"role": role, "content": content})
        self.logger_func(f"Added to conversation history: Role='{role}', Content='{content[:50]}...'")

    def get_conversation_history(self):
        return self._conversation_history

    def get_original_project_purpose(self):
        return self._original_project_purpose
    
    def set_original_project_purpose(self, purpose):
        self._original_project_purpose = purpose
        self.logger_func(f"Original project purpose set: '{purpose}'")

    def save_code(self, base_filename: str, content: str, file_extension: str = "py", description: str = None, operation_type: str = "saved", feature_context: str = None, llm_prompt: str = None, llm_diagnostic: str = None, llm_response: str = None, intent: str = None) -> str:
        full_filename = f"{base_filename}.{file_extension}"
        file_path = self.project_root / full_filename

        description_text = description or f"Code {operation_type} by LLM."
        if feature_context:
            description_text += f" | Context: {feature_context}"
        
        file_info = {
            "file_path": str(file_path),
            "filename": full_filename,
            "file_extension": file_extension,
            "description": description_text,
            "operation_type": operation_type,
            "content_preview": content[:200] + "..." if len(content) > 200 else content,
            "llm_prompt": llm_prompt,
            "llm_diagnostic": llm_diagnostic,
            "llm_response": llm_response,
            "intent": intent
        }
        self._saved_files.append(file_info)
        self.set_current_working_file(str(file_path)) 

        log_message = f"Code {operation_type}: Saved '{full_filename}'. Description: '{file_info['description']}'. Path: '{file_path}'."
        self.log_to_coordinator(log_message, "FILE_OPERATION")

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists
            file_path.write_text(content, encoding="utf-8")
            self.logger_func(f"Successfully wrote file: {file_path}")
        except Exception as e:
            error_msg = f"Error writing file {full_filename}: {str(e)}"
            self.logger_func(f"Error: {error_msg}", "ERROR")
            raise IOError(error_msg) from e

        return str(file_path)

    def get_current_working_file(self):
        return self._current_working_file

    def set_current_working_file(self, file_path: str):
        # Convert to relative path if possible for consistency
        try:
            rel_path = os.path.relpath(file_path, self.project_root)
            self._current_working_file = rel_path
        except ValueError:
            self._current_working_file = file_path
            
        self.logger_func(f"Current working file (focus) set to: {self._current_working_file}", "FOCUS_UPDATE")

    def suggest_filename(self, prompt: str, content_preview: str = "") -> str:
        """
        Suggests a sensible filename based on the user's prompt and conversation history.
        """
        # Simple rule-based suggestions first
        if "calculator" in prompt.lower(): return "calculator.py"
        if "solver" in prompt.lower(): return "solver.py"
        if "main" in prompt.lower(): return "main.py"
        if "test" in prompt.lower(): return "test_script.py"
        
        # Check history for context
        for turn in reversed(self._conversation_history):
            if turn['role'] == 'user':
                match = re.search(r'(?:file|filename|save to|into):\s*([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)', turn['content'], re.IGNORECASE)
                if match: return match.group(1).strip()

        # If it's a repair, we should already have a focus
        if self._current_working_file:
            return self._current_working_file

        return "new_script.py" # Final fallback

    def get_last_problematic_code(self):
        return self._last_problematic_code

    def set_last_problematic_code(self, code: str):
        self._last_problematic_code = code
        self.logger_func("Last problematic code content stored.")
        
    def get_last_warnings(self):
        return self._last_warnings

    def set_last_warnings(self, warnings: list[str]):
        self._last_warnings = warnings
        self.logger_func(f"Last warnings stored: {warnings}")

    def clear_last_warnings(self):
        self._last_warnings = []
        self.logger_func("Last warnings cleared.")

    def get_last_patch_result(self):
        return self._last_patch_result

    def set_last_patch_result(self, success: bool, message: str, patch_applied: bool = None):
        self._last_patch_result = {"success": success, "message": message, "patch_applied": patch_applied}
        self.logger_func(f"Last patch result set: Success={success}, Message='{message}', Applied={patch_applied}", "PATCH_RESULT")

    def get_last_validation_results(self):
        return self._last_validation_results

    def set_last_validation_results(self, results: list[dict]):
        self._last_validation_results = results
        self.logger_func(f"Last validation results stored: {results}")

    def clear_operation_state(self):
        self._last_patch_result = None
        self._last_validation_results = []
        self._last_warnings = []
        self._last_problematic_code = None
        self.logger_func("Operation state cleared.")

    def log_to_coordinator(self, message: str, log_level: str = "INFO"):
        # Use the provided logger function, assumed to be log_to_file
        self.logger_func(message, category=log_level)

    def get_saved_files(self):
        return self._saved_files

    def generate_user_message(self, file_path: str, action_summary: str, last_llm_response: str = None) -> str:
        file_info = next((f for f in self._saved_files if f["file_path"] == file_path), None)
        
        operation_type = file_info.get("operation_type", "processed") if file_info else "processed"
        description = file_info.get("description", "Code updated by LLM.") if file_info else "Code updated by LLM."
        intent = file_info.get("intent", None) if file_info else None

        # Determine dynamic next steps based on operation type and intent
        next_steps = "Review the changes and provide further instructions."
        if operation_type == "patched":
            next_steps = "Please verify the patch and test the functionality."
        elif operation_type == "rewritten":
            next_steps = "Review the rewritten code for correctness and integration."
        elif operation_type == "created":
            next_steps = "Consider integrating this new module or testing its functionality."
        elif operation_type == "saved":
            next_steps = "Review the saved file and integrate it as needed."
        
        # If intent is available and specific, tailor next steps further
        if intent == "coding" and "template" in description.lower():
            next_steps += " Review the template code and test its rendering."
        elif intent == "fix" and operation_type == "patched":
             next_steps += " Verify the patch addresses the reported issue."
        # Add more specific next steps based on intent/operation_type if needed

        message = f"""**Code Update Notification:**
A code file has been {operation_type}: `{file_path}`
**Summary:** {action_summary}
**Details:** {description}
"""
        # Include snippet of LLM response if available and relevant
        llm_context_snippet = ""
        # Check file_info first, then fallback to last_llm_response if available
        if file_info and file_info.get("llm_response"):
            llm_context_snippet = f"**LLM Context:** {file_info['llm_response'][:150]}..." # Truncate for brevity
        elif last_llm_response: 
            llm_context_snippet = f"**LLM Context:** {last_llm_response[:150]}..."
        
        if llm_context_snippet:
            message += llm_context_snippet

        message += f"""**Next Steps:** {next_steps}
"""
        if self._current_working_file:
            message += f"The LLM's current focus is now on: `{self._current_working_file}`"
        
        self.log_to_coordinator(f"Generated user message for {file_path}: {action_summary}", "USER_MESSAGE")
        return message

    def add_to_conversation_history(self, role, content):
        self._conversation_history.append({"role": role, "content": content})
        self.logger_func(f"Added to conversation history: Role='{role}', Content='{content[:50]}...'")

    def get_last_saved_file_info(self):
        # Return the last saved file info for potential use in main.py
        return self._saved_files[-1] if self._saved_files else None
    
    def clear_saved_files(self):
        self._saved_files = []
        self.logger_func("Saved files list cleared.")
    
    def get_saved_files(self):
        return self._saved_files
