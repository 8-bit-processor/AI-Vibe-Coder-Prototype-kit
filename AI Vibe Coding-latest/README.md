# AI Vibe Coding

AI Vibe Coding is Facade agent framework designed to assist with coding tasks using Large Language Models (LLMs). It features a robust feedback loop that allows the Facade to self-correct, run code, and learn from its own interaction history with the LLM by reinforcement from rewarding examples.

## Key Features
- **Autonomous Feedback Loop**: The agent can read, write, and execute code, feeding errors back into its next "thought" process.
- **Multi-Backend Support**: Seamlessly switch between Ollama (local) and OpenAI.
- **Heuristic Parsing**: Interprets natural language recommendations without requiring strict JSON formatting.  The llms preference for natural conversational interaction
- **Self-Learning**: Analyzes historical logs to improve filename detection, prompt effectiveness, and error recovery strategies thru reward and reinforcement. The user does the facade's work when it is not able to handle it or understand. 
- **Project Indexing**: Automatically maps project structures to provide accurate context to the LLM.
- **Session Reset**: Manually or automatically clear LLM context (hogwash) while preserving learning logs.  This frees the LLM context from irrelevant noise.
- **Internal Transparency**: View the exact messages the facade sends back to the LLM to understand and shape the interaction loop.

## Setup
1. **Requirements**:
   - Python 3.10+
   - `httpx`, `openai`, `questionary`, `rich`
2. **Installation**:
   ```bash
   pip install httpx openai questionary rich
   ```
3. **Running**:
   ```bash
   python main.py
   ```

## Usage
- **Prompt LLM**: Ask the agent to implement features or fix bugs.
- **Run Last Recommended Code**: Quickly execute and debug suggested scripts.
- **Setup Virtual Environment**: Create a localized environment for your project.
- **Reset LLM Context**: Clear conversational noise while keeping the project structure in focus.
- **Change Model**: Switch between available LLMs on the fly.
