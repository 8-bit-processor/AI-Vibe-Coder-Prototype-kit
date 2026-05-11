# Ollama Agent Coder

Ollama Agent Coder is an intelligent, context-aware CLI tool designed to streamline code development, bug fixing, and refactoring using LLMs via Ollama or OpenAI. It features a robust, modular architecture designed for stability and surgical code application.

## 🚀 Key Features

- **Expert Surgical Repair Engine**: A highly resilient matching engine that supports:
    1. **Exact Match**: Character-perfect replacement.
    2. **Normalized Match**: Ignores whitespace and blank line variations.
    3. **Contextual Match**: Anchors on function/class definitions.
    4. **Fuzzy Match (Tier 4)**: Uses `rapidfuzz` to match code blocks with 85%+ similarity.
    5. **Auto-Indentation**: Automatically adjusts patch indentation to match your project's style.
    6. **Conflict Detection**: Prevents overlapping or conflicting patches.
- **System Guard (AST Analysis)**: Proactively detects blocking constructs like infinite `while True` loops or `input()` calls that could hang your application when imported.
- **Continuous Context Visibility**: Automatically refreshes and displays the project state (files and metadata) for every prompt, ensuring the LLM always has an accurate "mental model."
- **Multi-Block Atomic Patching**: Applies multiple fixes in a single turn. If one block fails, the entire transaction is aborted to prevent file corruption.
- **Comprehensive Traceability**: Every decision, diagnostic report, and LLM prompt is timestamped and logged to `session.log` for full auditability.
- **Modern LLM Support**: Fully compatible with local Ollama models and the modern OpenAI v1.x asynchronous client.

## 🛠️ Prerequisites

- **Python**: 3.8 or higher.
- **Ollama**: [ollama.com](https://ollama.com/) (for local models).
- **OpenAI API Key** (optional): For cloud-based models.
- **Dependencies**: `rapidfuzz` (added for robust code matching).

## 📦 Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd ollama-agent-coder
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## 🖥️ Usage

Run the application:
```bash
python main.py
```

### Workflow:
1. **Choose Backend/Model**: Select your preferred model.
2. **Set Project Directory**: Point to your project; the tool will scan and summarize files automatically.
3. **Prompt**: Enter your request (e.g., "Fix the AttributeError in chatbot.py").
4. **Repair/Save**: The tool analyzes the request, generates a diagnostic report, and proposes surgical patches that you can apply with confidence.

## 📂 Project Structure

- `main.py`: Main orchestration loop.
- `refactor_engine.py`: Logic for intent classification and prompt building.
- `patch_engine.py`: Surgical Search/Replace patch application.
- `code_validator.py`: Syntax error detection.
- `llm/`: Client implementations.

## 📄 License
MIT License.
