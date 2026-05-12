# Ollama Agent Coder

Ollama Agent Coder is an intelligent, context-aware CLI tool designed to streamline code development, bug fixing, and refactoring using LLMs via Ollama or OpenAI. It features a robust, modular architecture designed for stability and surgical code application.

## 🚀 Key Features

-   **Enhanced Context Management (`patch_coordinator`):**
    *   Stores original project purpose and conversation history.
    *   Remembers problematic code blocks that triggered warnings.
    *   Proactively guides LLM focus on critical warnings and context for targeted fixes.
    *   Manages file naming, saving, and context recall for patching operations.
-   **System Guard (AST Analysis):** Proactively detects blocking constructs like infinite `while` loops (even with variable conditions) or `input()` calls that could hang your application on import.
-   **Intelligent Code Fixes:** LLM is prompted to prioritize fixing `SYSTEM GUARD WARNINGS` and can generate fixes for problematic code blocks, suggesting temporary filenames for unsaved code, and producing corrected code wrapped in `if __name__ == "__main__":` guards.
-   **Robust Code Extraction:** Reliably extracts Python code blocks, ignoring markdown comments and headers, and handles code with specific language tags (`python`, `py`).
-   **Expert Surgical Repair Engine**: A highly resilient matching engine that supports:
    *   **Exact Match**: Character-perfect replacement.
    *   **Normalized Match**: Ignores whitespace and blank line variations.
    *   **Contextual Match**: Anchors on function/class definitions.
    *   **Fuzzy Match (Tier 4)**: Uses `rapidfuzz` to match code blocks with 85%+ similarity.
    *   **Auto-Indentation**: Automatically adjusts patch indentation to match your project's style.
    *   **Conflict Detection**: Prevents overlapping or conflicting patches.
-   **Continuous Context Visibility**: Automatically refreshes and displays the project state (files and metadata) for every prompt, ensuring the LLM always has an accurate "mental model."
-   **Multi-Block Atomic Patching**: Applies multiple fixes in a single turn. If one block fails, the entire transaction is aborted to prevent file corruption.
-   **Comprehensive Traceability**: Every decision, diagnostic report, and LLM prompt is timestamped and logged to `session.log` for full auditability.
-   **Modern LLM Support**: Fully compatible with local Ollama models and the modern OpenAI v1.x asynchronous client.

## 🛠️ Prerequisites

-   **Python**: 3.8 or higher.
-   **Ollama**: [ollama.com](https://ollama.com/) (for local models).
-   **OpenAI API Key** (optional): For cloud-based models.
-   **Dependencies**: `rapidfuzz` (added for robust code matching).

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
1.  **Initial Setup**: Choose LLM backend, model, and set project directory. You'll be prompted for the project's original purpose.
2.  **Prompt**: Enter your request (e.g., "Fix the blocking input calls in the calculator script").
3.  **Context & Intent**: The tool refreshes context, determines intent, and incorporates warnings/history.
4.  **Repair/Save**: The tool analyzes the request, provides diagnostics, generates patches or full rewrites, and saves them intelligently using the `patch_coordinator`.

## 📂 Project Structure

-   `main.py`: Main orchestration loop, handles user interaction, context management, and LLM calls.
-   `refactor_engine.py`: Logic for intent classification and prompt building, now incorporating project purpose and conversation history.
-   `patch_engine.py`: Surgical Search/Replace patch application.
-   `code_validator.py`: Syntax error detection and robust blocking code analysis.
-   `code_extractor.py`: Reliable extraction of Python code blocks.
-   **`patch_coordinator.py`**: Manages state, context, warnings, problematic code, conversation history, and project purpose.
-   `llm/`: Client implementations.

## 📄 License
MIT License.
