# Ollama Agent Coder

Ollama Agent Coder is an intelligent, context-aware "Codebase Manager" designed to streamline development, bug fixing, and refactoring. It features a robust multi-agent architecture that provides architectural oversight, automated quality control, and surgical code application.

## 🚀 Key Features

-   **Project Supervisor (`project_supervisor`):** 
    *   **Architectural Oversight**: Scans the codebase to map classes, functions, and imports.
    *   **Logical Coordination**: Detects circular dependencies, bloated "God Modules," and redundant functionality.
    *   **Bird's-Eye Context**: Injects architectural alerts directly into the LLM's system prompt to ensure coordinated changes.
-   **Automated Quality Control (QC):**
    *   **Internal Review Pass**: Every piece of code is audited by a second "Senior QA Engineer" agent before being presented to you.
    *   **Self-Refinement**: Automatically corrects code that violates architectural alerts or fails to meet the original intent.
-   **Enhanced Context Management (`patch_coordinator`):**
    *   **Target Focus Persistence**: Remembers the specific file you are working on ("Target Focus") across multiple turns.
    *   **Secretary Logic**: Manages conversation history, project purpose, and problematic code blocks.
-   **Intelligent Filename Engine:**
    *   **Multi-Tier Detection**: Extracts filenames from prompt text, LLM headers, or code comments.
    *   **Brainstorming Fallback**: Automatically brainstorms short, descriptive names for new functionality using micro-LLM calls.
-   **Visual UX Enhancements:** 
    *   **Animated Status Spinners**: Real-time visual feedback for different processing phases (Thinking, Analyzing, Reviewing, Patching).
    *   **Modern CLI Interface**: Utilizes the `rich` library for professional panels, markdown formatting, and color-coded alerts.
-   **System Guard (AST Analysis):** Proactively detects blocking constructs like infinite loops or `input()` calls that could hang your application on import.
-   **Expert Surgical Repair Engine**: A highly resilient matching engine supporting:
    *   **Exact & Normalized Matching**: Ignores whitespace/newline variations.
    *   **Fuzzy Matching**: Uses `rapidfuzz` to match code blocks with 85%+ similarity.
    *   **Auto-Indentation**: Adjusts patch indentation to match your project's local style.
-   **Multi-Block Atomic Patching**: Applies multiple fixes in a single turn. If one block fails, the entire transaction is aborted to prevent file corruption.
-   **Fresh Audit Trails**: Automatically clears the `session.log` on startup to ensure a clean record for every development session.

## 🛠️ Prerequisites

-   **Python**: 3.8 or higher.
-   **Ollama**: [ollama.com](https://ollama.com/) (for local models).
-   **OpenAI API Key** (optional): For cloud-based models.
-   **Dependencies**: `rapidfuzz`, `rich`, `questionary`, `pathlib`.

## 📦 Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd ollama-agent-coder
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## 🖥️ Usage

Run the application:
```bash
python main.py
```

### Workflow:
1.  **Backend Selection**: Choose between local Ollama or OpenAI cloud models.
2.  **Architectural Audit**: The **Project Supervisor** scans your folder to understand module relationships.
3.  **Prompting**: Give instructions like "Create a math solver" or "Fix the bug in the auth module."
4.  **Review & Refine**: The agent analyzes, generates a diagnostic, produces code, and performs an internal **QC Pass** for refinement.
5.  **Focus-Aware Saving**: The agent suggests filenames and saves code, automatically updating its **Target Focus** for the next turn.

## 📂 Project Structure

-   `main.py`: The orchestration loop, managing user interaction and the multi-agent flow.
-   `project_supervisor.py`: Architectural mapping, dependency tracking, and coordination logic.
-   `refactor_engine.py`: Intent detection, context-aware prompt building, and the Automated QC loop.
-   `patch_coordinator.py`: State management, file focus tracking, and intelligent filename suggestions.
-   `patch_engine.py`: Resilient Search/Replace patch application with fuzzy matching.
-   `code_validator.py`: AST-based syntax validation and blocking code analysis (System Guard).
-   `code_extractor.py`: Multi-language code block and filename extraction engine.
-   `llm/`: Backend client implementations for Ollama and OpenAI.

## 📄 License
MIT License.
