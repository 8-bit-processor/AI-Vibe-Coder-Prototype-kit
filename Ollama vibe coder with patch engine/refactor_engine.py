from pathlib import Path

def format_history(coordinator, max_turns=5):
    """
    Formats the recent conversation history for inclusion in prompts.
    """
    history = coordinator.get_conversation_history()
    if not history:
        return ""
    
    formatted = "\n\n### Recent Conversation History ###\n"
    # Get last N turns
    recent = history[-max_turns:]
    for turn in recent:
        role = turn['role'].upper()
        content = str(turn['content'])
        # Increase truncation to 500 characters to keep more context
        truncated_content = content[:500] + ("..." if len(content) > 500 else "")
        formatted += f"[{role}]: {truncated_content}\n"
    formatted += "### End of History ###\n"
    return formatted

async def determine_intent(client, model, prompt, project_context):
    intent_messages = [
        {"role": "system", "content": (
            "Analyze the user's prompt and categorize it into one of the following intents:\n"
            "- 'fix': Reporting a bug, error, or something not working.\n"
            "- 'save': Explicitly asking to save code, write a file, or commit progress.\n"
            "- 'create': Asking to start a new project, file, or feature from scratch.\n"
            "- 'coding': Asking to modify existing code, add functionality, or refactor.\n"
            "- 'general': Asking a question, seeking explanation, or general conversation.\n"
            "Respond with ONLY the intent word (e.g., 'save')."
        )},
        {"role": "user", "content": f"Project Context:\n{project_context[:1000]}...\n\nUser Prompt: {prompt}"}
    ]
    response = await client.chat(model, intent_messages)
    return response.lower().strip().replace("'", "").replace('"', "")

def refine_instructions(base_instructions: str, intent: str, coordinator, supervisor_report: str) -> str:
    """
    Quality Control: Refines instructions based on current project state and supervisor findings.
    """
    refined = base_instructions
    
    # 1. Architectural Guardrails
    if "Circular dependency" in supervisor_report:
        refined += "\nQUALITY CONTROL ALERT: Circular dependencies detected. Your changes MUST NOT introduce new imports that worsen this. Prioritize interface-based decoupling.\n"
    
    if "bloated" in supervisor_report:
        refined += "\nQUALITY CONTROL ALERT: Some modules are bloated. If your change adds significant logic, consider suggesting a new utility module instead of adding to the God Module.\n"

    # 2. Focus & State Guardrails
    current_file = coordinator.get_current_working_file()
    last_patch = coordinator.get_last_patch_result()
    
    if last_patch and not last_patch.get("success"):
        refined += f"\nQUALITY CONTROL ALERT: The previous patch for '{current_file}' failed. You MUST change your approach. Do not repeat the same search/replace pattern.\n"
    
    # 3. Instruction Tuning for Intent
    if intent == 'create':
        refined += "\nCONSTRAINTS: You are creating NEW functionality. Ensure it follows the naming conventions and structure of the existing modules provided in the context.\n"
    elif intent == 'fix':
        refined += "\nCONSTRAINTS: You are in DEBUG mode. Be surgical. Do not refactor unrelated code. Only provide the fix.\n"

    return refined

def get_diagnostic_prompt(prompt, project_context, coordinator, supervisor_report="", previous_warnings: list[str] = None, last_patch_result: dict = None, last_validation_results: list[dict] = None):
    warnings_str = ""
    history_str = format_history(coordinator)
    
    # Prioritize previous warnings (from System Guard)
    if previous_warnings:
        warnings_str += "\nATTENTION CRITICAL: The previously generated code triggered the following SYSTEM GUARD WARNINGS. YOUR PRIMARY TASK IS TO DIAGNOSE AND FIX *THESE SPECIFIC WARNINGS* FIRST. YOU MUST PROVIDE A DIAGNOSTIC REPORT AND SUGGESTED CODE CHANGES THAT DIRECTLY ADDRESS THESE ISSUES.\n"
        for warn in previous_warnings:
            warnings_str += f"- {warn}\n"
    
    # Include last patch result if it indicates failure
    if last_patch_result and not last_patch_result.get("success", True):
        warnings_str += f"\nATTENTION CRITICAL: The last patch attempt failed. Patch details: Success={last_patch_result.get('success')}, Message='{last_patch_result.get('message', 'No message available')}', Applied={last_patch_result.get('patch_applied')}. Please diagnose why the patch failed and how to correct it.\n"

    # Include last validation results if they indicate errors
    if last_validation_results:
        error_found = False
        for res in last_validation_results:
            if res.get("type") == "syntax" and not res.get("is_valid"):
                warnings_str += f"\nATTENTION CRITICAL: The previously generated code had a SYNTAX ERROR: {res.get('detail', '')}. You must fix this syntax error.\n"
                error_found = True
            elif res.get("type") == "blocking_code" and not res.get("is_valid"):
                warnings_str += f"\nATTENTION CRITICAL: The previously generated code had a BLOCKING CODE WARNING: {res.get('detail', '')}. You must address this to prevent application hangs.\n"
                error_found = True
        if error_found:
            warnings_str += "\n"

    base_instructions = (f"You are a code debugger. {warnings_str}"
            f"{history_str}\n"
            f"{supervisor_report}\n"
            f"User request: '{prompt}'.\n"
            f"Identify the root cause of these issues and the specific logic changes needed to resolve them.\n"
            f"PROVIDE A STEP-BY-STEP DIAGNOSTIC REPORT focused on these issues.\n"
            f"Existing files (for context): {project_context}")
            
    return refine_instructions(base_instructions, 'fix', coordinator, supervisor_report)

def get_rewrite_prompt(prompt, diagnostic, project_context, coordinator, supervisor_report="", target_file: str = None, problematic_code_content: str = None, last_patch_result: dict = None, last_validation_results: list[dict] = None):
    target_file_hint = ""
    history_str = format_history(coordinator)
    
    if problematic_code_content:
        target_file_hint = f"\nATTENTION: The following code content (which triggered SYSTEM GUARD WARNINGS) needs to be fixed:\n```python\n{problematic_code_content}\n```\n"
        target_file_hint += "Your patch or rewrite MUST target this content. When providing ### FILE ###, suggest a temporary name like 'temp_fix.py'.\n"
    elif target_file:
        target_file_hint = f"\nThe user previously interacted with or generated code for the file: '{target_file}'. Your patch or rewrite should ideally target this file or suggest a very closely related file if absolutely necessary.\n"
    
    # Add context from patch result and validation results
    context_from_outcomes = ""
    if last_patch_result:
        context_from_outcomes += f"\nPrevious patch attempt outcome: Success={last_patch_result.get('success')}, Message='{last_patch_result.get('message', 'N/A')}', Applied={last_patch_result.get('patch_applied', 'N/A')}.\n"
    if last_validation_results:
        context_from_outcomes += "\nPrevious validation results: " + ", ".join([f"{r.get('type', 'N/A')}: {r.get('is_valid', 'N/A')}" for r in last_validation_results]) + ".\n"

    base_instructions = (f"Based on the diagnostic report: '{diagnostic}',\n"
            f"the original user request: '{prompt}',\n"
            f"{history_str}\n"
            f"{supervisor_report}\n"
            f"{target_file_hint}"
            f"{context_from_outcomes}\n"
            f"When determining the target file for patching or rewriting, meticulously analyze the provided diagnostic and project context to identify the most relevant file. If the target file is ambiguous or not explicitly stated, infer it from the bug description and the project's file structure. Aim to maintain architectural consistency and module integrity when suggesting changes.\n"
            f"create a SKELETAL patch. YOU MUST OUTPUT ONLY THE PATCH BLOCKS AND THE FILENAME. "
            f"Use exactly this format:\n\n"
            f"### FILE ###\n<the relative path of the file to be patched>\n\n"
            f"### SEARCH ###\n<paste the exact, complete, and literal code block from the original file that needs replacing>\n"
            f"### REPLACE ###\n<paste the exact new code that should replace it>\n\n"
            f"CRITICAL RULES:\n"
            f"1. NO PLACEHOLDERS: NEVER use meta-text like '<insert code>' or '<...>' in the SEARCH block.\n"
            f"2. EXACT MATCH: The content of the SEARCH block MUST exist character-for-character in the target file.\n"
            f"3. NO CONVERSATION: Output ONLY the requested patch blocks.\n"
            f"Original Context:\n{project_context}"
        )
        
    return refine_instructions(base_instructions, 'fix', coordinator, supervisor_report)

async def review_and_refine_code(client, model, original_prompt, generated_code, supervisor_report, intent, project_context):
    """
    Automated QC: Reviews the LLM's own output against architectural constraints and refines it if necessary.
    """
    review_messages = [
        {"role": "system", "content": (
            "You are a Senior Quality Assurance Engineer. Review the following code generated for a user request.\n"
            "CRITERIA:\n"
            "1. Does it violate any ARCHITECTURAL ALERTS in the Supervisor Report?\n"
            "2. Does it accurately fulfill the ORIGINAL PROMPT?\n"
            "3. Is it logically coordinated with the existing codebase?\n"
            "If the code is good, respond with 'APPROVED'. If not, provide a REFINED version of the code that fixes the issues. Respond with ONLY 'APPROVED' or the refined code blocks."
        )},
        {"role": "user", "content": (
            f"ORIGINAL PROMPT: {original_prompt}\n\n"
            f"SUPERVISOR REPORT: {supervisor_report}\n\n"
            f"GENERATED CODE:\n{generated_code}\n\n"
            f"PROJECT CONTEXT (PREVIEW):\n{project_context[:500]}..."
        )}
    ]
    
    review_response = await client.chat(model, review_messages)
    
    if "APPROVED" in review_response.upper()[:10]:
        return generated_code, False # Not refined
    else:
        return review_response, True # Refined

def build_system_prompt(intent, prompt, project_context, coordinator, supervisor_report=""):
    system_prompt = f"You are an expert coder. You have access to the following project files:\n\n{project_context}\n\n"
    system_prompt += "Your responses MUST be context-aware, considering the project's architecture, conventions, and file structure.\n\n"

    original_purpose = coordinator.get_original_project_purpose()
    if original_purpose:
        system_prompt += f"The overarching goal of this project is: '{original_purpose}'. Keep this in mind for all your tasks.\n\n"

    # CRITICAL: Project Supervision and Architectural Alerts
    if supervisor_report:
        system_prompt += f"{supervisor_report}\n\n"

    # CRITICAL: Filename and Context Awareness
    current_file = coordinator.get_current_working_file()
    if current_file:
        system_prompt += f"CONTEXT: You are currently working on or repairing the file: '{current_file}'. If your task is to fix or modify this file, ensure your code blocks reflect this.\n"
    else:
        system_prompt += "CONTEXT: You are starting a new task or file. Choose a filename that is idiomatic and descriptive of the functionality requested.\n"

    # Add relevant conversation history to the prompt
    system_prompt += format_history(coordinator)

    intent_instructions = ""
    if intent == 'fix':
        intent_instructions = f"\nINTENT: FIX/REPAIR. User reported: '{prompt}'. Focus on resolving the bug in the most relevant file (likely '{current_file or 'the file mentioned'}'). Provide a diagnostic then the FULL corrected code.\n"
    elif intent == 'create':
        intent_instructions = f"\nINTENT: CREATE NEW. User requested: '{prompt}'. Propose a NEW filename at the start of your code block (e.g. '# new_file.py').\n"
    elif intent == 'save':
        intent_instructions = f"\nINTENT: SAVE/COMMIT. User wants to save the current progress of '{current_file or 'the current work'}'.\n"
    elif intent == 'coding':
        intent_instructions = f"\nINTENT: MODIFY/FEATURE. User requested: '{prompt}'. Update the relevant files (starting with '{current_file or 'the most appropriate file'}').\n"
    else:
        intent_instructions = "\nINTENT: GENERAL. Provide a helpful explanation. If providing code, suggest a filename.\n"

    system_prompt += refine_instructions(intent_instructions, intent, coordinator, supervisor_report)
    
    system_prompt += "\nALWAYS wrap your code in markdown code blocks (using triple backticks) and include the intended filename as a comment on the first line of every code block (e.g., '# filename.py').\n"
    return system_prompt
