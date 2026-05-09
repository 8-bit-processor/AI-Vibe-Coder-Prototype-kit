# AI Agent Coder 

A simple, iterative AI agent that helps you build projects using Ollama or other LLM's API
Starts the code project for iterative vibe project by guiding AI with plain English.

## Features

- **Streaming Responses**: See the code being generated in real-time.
- **Self-Correction**: Automatically checks Python syntax and retries if errors are found.
- **Environment Configuration**: Easily configure your model and endpoint via a `.env` file.
- **Robust Model Selection**: Dynamically fetches available models from your Ollama instance.
- **Smart Context**: Provides the LLM with relevant file contents while ignoring unnecessary folders.

## Setup

1.  **Install dependencies**:
    ```bash
    pip install httpx questionary rich python-dotenv
    ```

2.  **Configure Ollama**:
    Ensure Ollama is running and you have a `.env` file with:
    ```env
    OLLAMA_MODEL=llama3:latest
    OLLAMA_ENDPOINT=http://localhost:11434/api/chat
    ```

3.  **Run**:
    ```bash
    python main.py
    ```

## How it works

1.  **Architect Phase**: The LLM analyzes your request and decides which file needs to be modified or created.
2.  **Implementation Phase**: The LLM generates the complete code for that file.
3.  **Validation Phase**: If it's a Python file, the agent performs a syntax check. If it fails, it asks the LLM to fix the error and tries again.
4.  **Save Phase**: The validated code is saved to the disk.
   

ollama_coder/ 
├── main.py # Entry point 
├── cli.py # CLI interaction logic 
├── llm/  
  ├── init.py │ 
  ├── base.py # Base LLM interface  
  ├── ollama_client.py # Ollama-specific implementation
  ├── openai_client.py # OpenAI-specific implementation
  └── hf_client.py # Hugging Face implementation 
├── code_extractor.py # Code block extraction logic 
├── project_manager.py # Project dir handling 
└── utils.py # Helper functions

Modular Design: 
  base.py Ensures consistent interface for any LLM 
  ollama_client.py, openai_client.py Easy to add more clients 
  code_extractor.py Reusable logic 
  cli.py Clean separation of concerns, easy logic to add more features 
  main.py Entry point that orchestrates everything

