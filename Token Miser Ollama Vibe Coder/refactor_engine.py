import re
from logger_utils import log_to_file

def build_system_prompt(programming_language, intent, project_context):
    """
    Expert coder system instruction for implementation tasks.
    Used when the agent is expected to write or modify code.
    """
    return (
        f"You are an expert software engineer. Your task is to provide functional, complete, idiomatic {programming_language} code. "
        "Make reasonable assumptions based on the provided project context if needed. "
        "If you are rewriting a file, return the COMPLETE file content in a single code block. "
        f"### PROJECT INTENT ###: {intent} \n ### CONTEXT ###: {project_context}"
    )

def build_audit_prompt(intent, project_context):
    """
    System instruction for repository analysis and technical audits.
    Focuses on reporting and analysis without generating code, ensuring safety.
    """
    return (
        "You are an expert technical auditor. Your task is to provide a comprehensive, "
        "analytical report of the project structure, code health, and architectural patterns. "
        "Your analysis should be grounded in the overall goal of the project. "
        "DO NOT provide code blocks or scripts. Focus exclusively on textual analysis, "
        "identifying potential risks, and suggesting improvements. "
        f"### PROJECT PURPOSE ###: {intent} \n"
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
