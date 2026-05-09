ollama_coder/
├── main.py                    # Entry point
├── cli.py                     # CLI interaction logic
├── llm/
│   ├── __init__.py
│   ├── base.py                # Base LLM interface
│   ├── ollama_client.py       # Ollama-specific implementation
│   ├── openai_client.py       # OpenAI-specific implementation
│   └── hf_client.py           # Hugging Face implementation
├── code_extractor.py          # Code block extraction logic
├── project_manager.py         # Project dir handling
└── utils.py                   # Helper functions


Modular Design:
    base.py	Ensures consistent interface for any LLM
    ollama_client.py, openai_client.py	Easy to add more clients
    code_extractor.py	Reusable logic
    cli.py	Clean separation of concerns, easy logic to add more features
    main.py	Entry point that orchestrates everything