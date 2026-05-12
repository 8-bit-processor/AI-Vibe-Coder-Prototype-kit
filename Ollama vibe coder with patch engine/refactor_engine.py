from pathlib import Path

async def determine_intent(client, model, prompt, project_context):
    intent_messages = [
        {"role": "system", "content": "Analyze the user's prompt. Determine if the user is asking a general question ('general'), asking for code modifications/features ('coding'), or reporting/asking to fix a bug ('fix'). Respond with only one word: 'general', 'coding', or 'fix'.\n\n" + project_context},
        {"role": "user", "content": prompt}
    ]
    return await client.chat(model, intent_messages)

def get_diagnostic_prompt(prompt, project_context, previous_warnings: list[str] = None):
    warnings_str = ""
    if previous_warnings:
        warnings_str = "ATTENTION CRITICAL: The previously generated code triggered the following SYSTEM GUARD WARNINGS. YOUR PRIMARY TASK IS TO DIAGNOSE AND FIX *THESE SPECIFIC WARNINGS* FIRST. YOU MUST PROVIDE A DIAGNOSTIC REPORT AND SUGGESTED CODE CHANGES THAT DIRECTLY ADDRESS THESE ISSUES.\n"
        for warn in previous_warnings:
            warnings_str += f"- {warn}\n"
        warnings_str += "\n"
        
        # When warnings are present, make them the focal point of the prompt
        return (f"You are a code debugger. {warnings_str}"
                f"User request: '{prompt}'. "
                f"Identify the root cause of these warnings and the specific logic changes needed to resolve them. "
                f"PROVIDE A STEP-BY-STEP DIAGNOSTIC REPORT focused on these warnings. "
                f"Existing files (for context): \n{project_context}")
    else:
        # Original behavior if no warnings
        return f"You are a code debugger. Analyze the following code and user report: '{prompt}'. Identify the root cause and the specific logic changes needed. PROVIDE A STEP-BY-STEP DIAGNOSTIC REPORT. \n\nExisting files:\n{project_context}"

def get_rewrite_prompt(prompt, diagnostic, project_context, target_file: str = None, problematic_code_content: str = None):
    target_file_hint = ""
    if problematic_code_content:
        target_file_hint = f"ATTENTION: The following code content (which triggered SYSTEM GUARD WARNINGS) needs to be fixed:\n```python\n{problematic_code_content}\n```\n"
        target_file_hint += "Your patch or rewrite MUST target this content. When providing ### FILE ###, suggest a temporary name like 'temp_fix.py'.\n\n"
    elif target_file:
        target_file_hint = f"The user previously interacted with or generated code for the file: '{target_file}'. Your patch or rewrite should ideally target this file or suggest a very closely related file if absolutely necessary.\n\n"
    
    return (
        f"Based on the diagnostic report: '{diagnostic}', and the original user request: '{prompt}', "
        f"{target_file_hint}"
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

def build_system_prompt(intent, prompt, project_context, coordinator):
    system_prompt = f"You are an expert coder. You have access to the following project files:\n\n{project_context}\n\n"
    
    # Add original project purpose to the prompt
    original_purpose = coordinator.get_original_project_purpose()
    if original_purpose:
        system_prompt += f"The overarching goal of this project is: '{original_purpose}'. Keep this in mind for all your tasks.\n\n"

    # Add relevant conversation history to the prompt (e.g., last few turns)
    conversation_history = coordinator.get_conversation_history()
    if conversation_history:
        # Get last 5 turns or so to keep context manageable
        recent_history = conversation_history[-5:] 
        system_prompt += "Here is a summary of our recent conversation:\n"
        for turn in recent_history:
            # Ensure content is a string before truncating
            content_str = str(turn['content'])
            system_prompt += f"  {turn['role']}: {content_str[:100]}...\n" # Truncate content for brevity
        system_prompt += "\n"

    if 'fix' in intent:
        system_prompt += f"The user reported a bug: '{prompt}'. First, analyze and provide a diagnostic report. Then, provide the FULL, corrected source code."
    elif 'coding' in intent:
        system_prompt += f"The user requested: '{prompt}'. Modify the existing code appropriately. Provide the complete, updated code in markdown code blocks. Explain your logic briefly."
    else:
        system_prompt += " Provide a helpful explanation for the user's inquiry about the codebase."
    return system_prompt
