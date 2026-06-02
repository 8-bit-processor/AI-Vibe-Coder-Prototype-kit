import re
from utils.logger_utils import log_to_file

def build_system_prompt(programming_language, intent, project_context, num_modules=2):
    """
    Expert coder system instruction for implementation tasks.
    Focuses the LLM on the immediate task, goal, and provided context.
    """
    capabilities = ""
    if num_modules > 1:
        capabilities = (
            "### CAPABILITIES ###\n"
            "If you need more information about the project to complete your task, you can request it by including one of the following commands in your response:\n"
            "- [REQUEST_CONTEXT: architecture] -> Get a summary of the project structure and symbols.\n"
            "- [REQUEST_CONTEXT: dependencies] -> Get the project's dependency graph.\n"
            "- [REQUEST_CONTEXT: file_contents(filename)] -> Get the full content of a specific file.\n\n"
        )

    return (
        f"Provide functional, complete, and idiomatic {programming_language} code that satisfies the request.\n\n"
        f"{project_context}\n\n"
        f"{capabilities}"
        "### GUIDELINES ###\n"
        "1. ALWAYS provide the COMPLETE file content in your code blocks. Never use placeholders like '// ... existing code'.\n"
        "2. Ensure all necessary imports are included.\n"
        "3. Follow the project's existing style and patterns found in the context.\n"
        "4. Your code will be automatically validated. If it fails, you will be given the error and a chance to fix it.\n\n"
        f"### HIGH-LEVEL PROJECT GOAL ###\n{intent}\n"
    )

def build_audit_prompt(intent, project_context):
    """
    System instruction for repository analysis and technical audits.
    """
    return (
        "Provide a comprehensive, analytical report of the project structure, code health, and architectural patterns. "
        "Focus exclusively on textual analysis, identifying potential risks, and suggesting improvements based on:\n"
        f"### PROJECT SCOPE ###: {intent}\n"
        f"### CONTEXT ###: {project_context}"
    )

def get_diagnostic_prompt(prompt, project_context, previous_warnings=None, **kwargs):
    warnings = "".join(previous_warnings) if previous_warnings else 'None'
    return f"""
### CONTEXT ###
{project_context}

### MISSION ###
{prompt}
ERRORS: {warnings}

PROVIDE A COMPLETE CODE FIX.
"""

def get_rewrite_prompt(prompt, diagnostic, project_context,  target_file=None, **kwargs):
    return f"""
### CONTEXT ###
{project_context}

### TASK ###
{prompt}
DIAGNOSTIC: {diagnostic}
TARGET: {target_file}

Provide the COMPLETE updated code for {target_file}. Return ONLY a single code block.
"""
