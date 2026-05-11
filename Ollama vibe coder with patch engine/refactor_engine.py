from pathlib import Path

async def determine_intent(client, model, prompt, project_context):
    intent_messages = [
        {"role": "system", "content": "Analyze the user's prompt. Determine if the user is asking a general question ('general'), asking for code modifications/features ('coding'), or reporting/asking to fix a bug ('fix'). Respond with only one word: 'general', 'coding', or 'fix'.\n\n" + project_context},
        {"role": "user", "content": prompt}
    ]
    return await client.chat(model, intent_messages)

def get_diagnostic_prompt(prompt, project_context):
    return f"You are a code debugger. Analyze the following code and user report: '{prompt}'. Identify the root cause and the specific logic changes needed. PROVIDE A STEP-BY-STEP DIAGNOSTIC REPORT. \n\nExisting files:\n{project_context}"

def get_rewrite_prompt(prompt, diagnostic, project_context):
    return (
        f"Based on the diagnostic report: '{diagnostic}', and the original user request: '{prompt}', "
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

def build_system_prompt(intent, prompt, project_context):
    system_prompt = f"You are an expert coder. You have access to the following project files:\n\n{project_context}\n\n"
    if 'fix' in intent:
        system_prompt += f"The user reported a bug: '{prompt}'. First, analyze and provide a diagnostic report. Then, provide the FULL, corrected source code."
    elif 'coding' in intent:
        system_prompt += f"The user requested: '{prompt}'. Modify the existing code appropriately. Provide the complete, updated code in markdown code blocks. Explain your logic briefly."
    else:
        system_prompt += " Provide a helpful explanation for the user's inquiry about the codebase."
    return system_prompt
