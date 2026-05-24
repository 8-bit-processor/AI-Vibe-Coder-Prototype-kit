# Ollama Agent Coder Architecture

The Ollama Agent Coder is a lean, high-signal architecture designed for autonomous agentic coding. It is built on the philosophy that **architectural clarity = LLM intelligence**. Every module serves a specific purpose; anything else is considered "hogwash" and is stripped away to keep the agent focused.

## Core Modules & Justification

| Module | Purpose | Why it is NOT Hogwash |
| :--- | :--- | :--- |
| `SessionOrchestrator` | Central system hub | Essential lifecycle manager; prevents state fragmentation across engines. |
| `ContextData` | High-signal state container | Eliminates prompt bloat by surfacing only mission-critical errors and objectives. |
| `ExecutionEngine` | "Act & Validate" engine | Mandatory orchestrator for the sandbox-verify-commit loop; prevents production corruption. |
| `ContextEngine` | Repository mapping | Provides "Pull-on-Demand" intelligence, keeping the LLM focused until it *needs* structure. |
| `PatchCoordinator` | File guardian | Ensures all changes are atomic and reversible; prevents corrupted state in a fast-paced loop. |

---

## The "Anti-Hogwash" Philosophy

We actively resist "architectural ceremony." Our modules interact via **circular referencing** to avoid the "hogwash" of deep, complex dependency trees that complicate function signatures and make the logic harder for an LLM to navigate.

### Direct Feedback Loops
*   **Why it's essential:** In traditional systems, diagnostic layers (intermediate reports) add ceremony. Here, we inject the raw error directly into the LLM’s context. This leverages the agent's innate reasoning rather than requiring an "agent-to-agent" intermediate layer (which is pure hogwash).

### Autonomous Pull Protocol
*   **Why it's essential:** Instead of providing a "one-size-fits-all" dump of context, we provide the bare minimum. By allowing the LLM to request context (e.g., `[REQUEST_CONTEXT: architecture]`), we keep the prompt window clean, saving tokens and keeping the LLM’s "attention heads" focused.

---

## Interaction Flow

1.  **Initialize:** `Orchestrator` binds the components, creating a shared session state.
2.  **Task:** The `ExecutionEngine` triggers an iterative fix loop.
3.  **Validate:** Code is verified in a sandbox (`.tmp/staging`).
4.  **Loop:** If an error occurs, it is fed back to the LLM as the *exclusive* priority for the next iteration, bypassing all intermediate, low-signal "diagnostic" processes.
5.  **Pull:** If the LLM lacks information, it triggers an autonomous `[REQUEST_CONTEXT]` pull, which is fulfilled instantly by the engine without human interference.

**This is a high-signal architecture. Do not introduce "Just-in-Case" logic, redundant abstractions, or ceremonial wrappers. If it doesn't solve a problem, it is hogwash.**
