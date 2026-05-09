# AI Agent Coder 

A simple, iterative AI agent that helps vibe coders to build projects using Ollama or other LLM's API
Starts the code project for iterative vibe project by guiding AI with plain English.
Agent Coder is an chat interactive command line interface tool designed to streamline your coding workflow using Large Language Models (LLMs). It allows you to prompt models via Ollama or OpenAI, view the generated code in a formatted terminal interface, and selectively save code blocks directly to your project files.

*** At this point this is just the base code for starting a project- there is still a lot of work to be done
and need to work out the iterative features***

##  Features

- **Multi-Backend Support**:  switch between local models via **Ollama** and cloud-based models via **OpenAI**.
- **Interactive CLI**: Powered by `questionary` for a smooth, guided user experience.
- **Code Extraction**: Automatically identifies and extracts markdown code blocks from LLM responses.
- **Surgical File Saving**: Choose which generated code blocks to save and specify filenames on the fly.
- **Rich Visuals**: Uses `rich` to provide syntax highlighting and clean panel-based layouts in the terminal.
- **Extensible Architecture**: Built using modules with an abstract base class system, making it easy to add new LLM providers.

##  Prerequisites

- **Python**: 3.8 or higher.
- **Ollama** (optional): Install from [ollama.com](https://ollama.com/) if you plan to use local models.
- **OpenAI API Key** (optional): Required if you plan to use OpenAI models.

##  Installation

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

Run the application using Python:

```bash
python main.py
```

### Workflow:
1. **Select Backend**: Choose between "Ollama" or "OpenAI".
2. **Model Selection**: Pick from the list of available models on your chosen backend.
3. **Set Project Directory**: Specify where you want the generated files to be saved.
4. **Prompt**: Tell the agent what you want to code (e.g., "Create a Python script to scrape news headlines").
5. **Review & Save**: View the generated response and choose whether to save specific code blocks to your project.

## 📂 Project Structure

- `main.py`: The central orchestration script.
- `cli.py`: Handles terminal interactions and user input.
- `code_extractor.py`: Utility for parsing code blocks from markdown.
- `llm/`: Contains the LLM client implementations.
  - `base.py`: The abstract base class for all LLM clients.
  - `ollama_client.py`: Client for interacting with the Ollama API.
  - `openai_client.py`: Client for interacting with the OpenAI API.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request or open an issue for any bugs or feature requests.

## 📄 License

This project is open-source and available under the MIT License.
