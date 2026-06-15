# Project Structure

This document outlines the architecture and components of the AI Vibe Coding assistant CLI.

## Core Orchestrator
- `main.py`: Contains `FacadeSessionOrchestrator`, the central hub managing the session lifecycle, LLM interaction loop, and action execution.

## Services (src/services/)
- `base.py`: Defines `BaseService`, the parent class for all services, providing access to the `orchestrator`.
- `code_management.py`: Implements `CodeManagementServices`. Handles file I/O, project structure indexing, and directory scanning (ignoring junk files/directories).
- `file_clerk.py`: Implements `FileClerk`. Executes actions recommended by the LLM (saving files, running shell commands) and manages user confirmations via `questionary`.
- `LLM_CLI_interface.py`: Implements `LLM_CLI_Interface`. A heuristic-based engine that parses LLM responses for intent, detects filenames, checks Python syntax, and manages conversation drift (Support Mode).
- `recordkeeper.py`: Implements `Recordkeeper`. Logs interaction history (prompts, responses, actions) as JSON files in the `history/` directory.

## LLM Clients (llm/)
- `base.py`: Defines the base interface for LLM client implementations.
- `ollama_client.py`: Implements the `OllamaClient` for interacting with Ollama-based models.
- `openai_client.py`: Implements the `OpenAIClient` for interacting with OpenAI API models.

## Heuristic & Learning Engine (communication_lessons/heuristic_engine/)
This module provides the "self-learning" capability to the facade.
- `evaluator.py`: The decision engine. Evaluates LLM output against rules defined in `data/rules.json` using regex, keyword similarity, and semantic matching.
- `similarity_transformer.py`: Provides tools for calculating semantic similarity to match LLM responses to learned patterns.
- `transformer_matcher.py`: Optional component for advanced semantic matching using sentence transformers (if installed).
- `data/rules.json`: A human-readable JSON file storing the rules, hard patterns, and learned exemplars.

## Utilities
- `cli.py`: Handles CLI-specific interactions, such as selecting models and project directories.
- `code_extractor.py`: Utility functions for extracting Markdown code blocks from LLM raw text responses.
