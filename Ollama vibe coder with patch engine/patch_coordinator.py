import os
from typing import List, Dict, Any, Optional

class PatchCoordinator:
    def __init__(self, project_root: str = ""):
        self.project_root = project_root if project_root else os.getcwd()
        self._saved_files: List[Dict[str, Any]] = []
        self._current_working_file: Optional[str] = None
        self._last_warnings: List[str] = [] # Added to store recent warnings
        self._last_problematic_code_content: Optional[str] = None # Added to store the content of the problematic code
        self._original_project_purpose: Optional[str] = None # Added to store the overall project goal
        self._conversation_history: List[Dict[str, str]] = [] # Added to store user prompts and LLM responses

    def set_last_warnings(self, warnings: List[str]):
        """
        Sets the list of the most recent warnings detected.
        """
        self._last_warnings = warnings

    def get_last_warnings(self) -> List[str]:
        """
        Retrieves the list of the most recent warnings detected.
        """
        return self._last_warnings

    def set_last_problematic_code(self, code_content: str):
        """
        Sets the content of the last problematic code block that triggered warnings.
        """
        self._last_problematic_code_content = code_content

    def get_last_problematic_code(self) -> Optional[str]:
        """
        Retrieves the content of the last problematic code block.
        """
        return self._last_problematic_code_content

    def set_original_project_purpose(self, purpose: str):
        """
        Sets the high-level original purpose/goal of the project.
        """
        self._original_project_purpose = purpose

    def get_original_project_purpose(self) -> Optional[str]:
        """
        Retrieves the high-level original purpose/goal of the project.
        """
        return self._original_project_purpose

    def add_to_conversation_history(self, role: str, content: str):
        """
        Adds a turn to the conversation history.
        Role can be 'user' or 'llm'.
        """
        self._conversation_history.append({"role": role, "content": content})

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """
        Retrieves the full conversation history.
        """
        return self._conversation_history

    def clear_last_warnings(self):
        """
        Clears the list of recent warnings and the last problematic code content.
        (Does NOT clear conversation history or project purpose as they are session-long)
        """
        self._last_warnings = []
        self._last_problematic_code_content = None

    def save_code(self, base_filename: str, content: str, file_extension: str = "py", description: str = None) -> str:
        """
        Saves LLM-generated code to the project folder with the correct naming and extension.
        Stores metadata about the saved file.
        """
        full_filename = f"{base_filename}.{file_extension}"
        file_path = os.path.join(self.project_root, full_filename)

        os.makedirs(os.path.dirname(file_path), exist_ok=True) # Ensure directory exists

        with open(file_path, "w") as f:
            f.write(content)

        file_info = {
            "file_path": file_path,
            "filename": full_filename,
            "file_extension": file_extension,
            "description": description,
            "content_preview": content[:200] + "..." if len(content) > 200 else content # Store a preview
        }
        self._saved_files.append(file_info)
        self.set_current_working_file(file_path) # Automatically set as current working file

        return file_path

    def set_current_working_file(self, file_path: str):
        """
        Sets the current file the LLM is focused on.
        """
        self._current_working_file = file_path

    def get_current_working_file(self) -> Optional[str]:
        """
        Retrieves the path of the current file the LLM is focused on.
        """
        return self._current_working_file

    def get_saved_files_info(self) -> List[Dict[str, Any]]:
        """
        Retrieves information about all files saved through the coordinator.
        """
        return self._saved_files

    def generate_user_message(self, file_path: str, description: str, next_steps: str) -> str:
        """
        Generates a standardized message for the user about newly created/modified code.
        """
        message = f"""**Code Update Notification:**
A new code file has been processed at: `{file_path}`
"""
        if description:
            message += f"""**Description:** {description}
"""
        message += f"""**Next Steps:** {next_steps}
"""
        message += f"The LLM's current focus is now on: `{self._current_working_file}`"
        return message

# Example Usage (for testing/demonstration)
if __name__ == "__main__":
    # Create a dummy project root for testing
    test_project_root = "test_project"
    os.makedirs(test_project_root, exist_ok=True)

    coordinator = PatchCoordinator(project_root=test_project_root)

    # Save a Python file
    python_code = """def hello_world():
    print('Hello, world!')"""
    py_file_path = coordinator.save_code("hello", python_code, "py", "A simple Python hello world function.")
    print(f"Saved: {py_file_path}")

    # Save a Markdown file
    md_content = """# Project Notes
This is a test markdown file."""
    md_file_path = coordinator.save_code("notes", md_content, "md", "Some notes for the project.")
    print(f"Saved: {md_file_path}")

    # Get current working file
    print(f"Current working file: {coordinator.get_current_working_file()}")

    # Get info about all saved files
    print("""
Saved Files Info:""")
    for info in coordinator.get_saved_files_info():
        print(info)

    # Generate a user message
    user_msg = coordinator.generate_user_message(
        py_file_path,
        "The initial hello_world function has been created.",
        "Please review the code and provide feedback for further development."
    )
    print(f"""
--- User Message ---
{user_msg}""")

    # Clean up test files and directory
    os.remove(py_file_path)
    os.remove(md_file_path)
    os.rmdir(test_project_root)
