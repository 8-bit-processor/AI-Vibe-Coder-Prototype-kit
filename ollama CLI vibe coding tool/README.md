# Ollama Agent Coder CLI

A semi-autonomous, token-efficient, and goal-oriented CLI agent designed for vibe software creation using Ollama or other API LLM capabilities to perform coding, architectural analysis, and automated repairs within a local development environment.  When using Ollama the code produced stays local and secure. 

## Project Goal
The primary objective of this project is to provide a robust, context-aware coding assistant that maximizes LLM performance through selective, on-demand context injection and a structured task-focused workflow.

There are some unused codeblocks that are being saved for later when I have time to decide after I have read thru the programming logic.
AI coding has been a tremendous help in making this but unfortunately it also put some hogwash code in here.

## Organizational Structure
The codebase has been refactored for improved maintainability and readability:

- **Root (`./`)**: Main application entry and high-level orchestration.
    - `main.py`: Entry point and CLI loop.
    - `session_orchestrator.py`: Manages the session lifecycle.
    - `execution_engine.py`: Controls code generation, validation, and execution cycles.
- **`attention_context/`**: Manages selective context selection and dependency mapping.
    - `context_data.py`: Centralized container for LLM-relevant state.
    - `context_engine.py`: Scans and scores project relevance for LLMs.
    - `dependency_manager.py`: Resolves and maps module imports.
- **`code_surgery/`**: Handles safe, staged code modifications.
    - `patch_coordinator.py`: Manages staging, backups, and commits.
    - `block_extractor.py`: Isolates code sections for surgical application.
    - `patch_engine.py`: Applies LLM-generated patches.
- **`llm_tools_and_analysis/`**: Tools for analysis, validation, and prompting.
    - `coder_agent.py`: High-level agent logic.
    - `code_extractor.py`: Extracts code from LLM responses.
    - `code_validator.py`: AST-based safety checks for generated code.
    - `llm_prompting_engine.py`: Manages prompt templates and structures.
    - `validator_engine.py`: Integrated validation workflow.
    - `big_repository_management_tools/`: Scalable analysis tools.
- **`llm/`**: Interface wrappers for LLM backends (Ollama/OpenAI).
- **`utils/`**: Shared utilities (logger, CLI helpers).

## The Lower-Level Foundation (The "Engine Room")

  1. `Safety & Persistence (code_surgery/patch_coordinator.py)`
  This is the most "low-level" part of the system. It handles the actual physical writing of files.
   * The Sandbox: Look for the stage_code method. It ensures no code touches your project until it’s been verified in .tmp/staging.
   * The Insurance: Look for create_backup. It takes a snapshot of your file before any change is committed.
   * The Resolver: The _resolve_path method is a security gate; it prevents the LLM from trying to write files outside of your project folder (directory traversal).

  2. `Intelligence & Mapping (attention_context/context_engine.py)`
  This is the "eye" of the system. It reads your code and decides what is important.
   * The Scanner: scan_project uses Python's ast (Abstract Syntax Tree) to "understand" your code as objects (classes/functions) rather than just text.
   * The Ranker: get_smart_context is the heart of the logic. It assigns "relevance scores" to files so the LLM doesn't get overwhelmed with irrelevant data.
   * The Minifier: prune_code surgically removes comments and docstrings from secondary files to squeeze more logic into the LLM's memory.

  3. `Execution & Verification (execution_engine.py)`
  This is the "hands" of the system. It bridges the gap between the LLM and your computer.
   * The Sandbox Runner: Look at verify_code (in llm_tools_and_analysis/validator_engine.py, called by the engine). It doesn't just check syntax; it actually tries to run the code for a few seconds to see if it crashes.
   * The Retry Loop: _generate_with_retry is the central "Act & Validate" loop. It’s where the system tries, fails, learns from the error, and tries again.

### High-Level Logic Flow Summary

   1. `Initialization (main.py):`
       * Steps 1-3: Handles LLM backend selection (Ollama/OpenAI), model selection, and project directory setup.
       * Step 5: Initializes the SessionOrchestrator, which serves as the central hub and ensures synchronization of global state.
   2. `Session Loop (main.py):`
       * Action Menu: The decision point where the user chooses between Coding, Auditing, or Launching the app.
   3. `Context Management & Synchronization (attention_context/):`
       * **Single Source of Truth**: The `ContextData` container maintains the authoritative state (Goal, Task, Errors) for the session.
       * **Drift Prevention**: Both the high-level `Project Goal` and the immediate `Current Task` are injected into every prompt to keep the LLM focused.
       * **Smart Context**: The `ContextEngine` ranks project files by relevance using keyword matching and dependency graph propagation, pruning non-essential code to stay within token limits.
   4. `Act & Validate Cycle (execution_engine.py):`
       * Step A-C: Prepares the prompt, sends it to the LLM, and handles any autonomous context requests (e.g., the LLM asking for specific file contents).
       * Step D (Sandbox Staging): Extracted code is written to a temporary "sandbox" area (.tmp/staging) to prevent affecting the live project.
       * Step E (Validation): The staged code is run in a subprocess to check for syntax errors or runtime crashes.
       * Step F (Commit): If validation passes, the code is promoted from the sandbox to the project root (with an automatic backup created first by the PatchCoordinator).
   5. `Execution & Feedback:`
       * The user can launch the app. If it crashes, the runtime error is captured and fed back into the next "Fix Cycle" to inform the LLM of what went wrong.


## The code that sends the messages to the LLM is organized into two layers: the orchestration layer (which prepares the data) and the client layer (which handles the network request).

  1. `The Orchestration Layer`
  The actual call to the LLM happens in `execution_engine.py` inside the `_generate_with_retry method`

   * File: execution_engine.py
   * Line: ~174
   * Code:

   1     # === STEP B: LLM GENERATION ===
   2     response_text = await self.client.chat(self.model, messages)

  2. `The Client Layer (The Network Request)`
  The`self.client.chat` call above refers to one of the backend implementations in the llm_choices/ directory, depending
  on which backend you selected at startup:

   * For `Ollama:` llm_choices/ollama_client.py
       * It uses httpx to send a POST request to http://localhost:11434/api/chat.
   * For `OpenAI:` llm_choices/openai_client.py
       * It uses the official openai Python library to communicate with their API.

  3. `Full Repository Audit`
  If you are using the "Analyze Entire Repository" action, the call is also located in `execution_engine.py` but inside
  the `run_general_cycle` method (around line 323).


## Key Architectural Principles
- **Lean Prompting**: Prompts are structured into explicit `### PROJECT GOAL ###`, `### CONTEXT ###`, and `### TASK ###` sections to focus LLM attention and optimize token usage.
- **ContextData**: Acts as a high-signal container for supplemental LLM context, reducing prompt bloat.
- **Sandbox Staging**: All LLM-generated changes must pass through the `code_surgery` sandbox before being committed to the project.
- **Persistence**: Project goals are saved locally to `.project_goal` files within the repository to ensure persistence across application restarts.

## Setup & Dependencies
1. **Requirements**: Ensure Python 3.9+ is installed.
2. **Dependencies**: Install via `pip install -r requirements.txt`.
3. **Environment**: Use `Settings (Menu) -> Setup Venv` to create a project-specific virtual environment.

## Usage
Launch the CLI:
```bash
python main.py
```
Follow the interactive prompts to select your backend, model, and project directory.

