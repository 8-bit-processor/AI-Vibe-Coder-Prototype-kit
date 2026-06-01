"""
Logging utilities for the Ollama Agent Coder.

This module provides a centralized logging system that writes to 'session.log'.
It includes specialized formatting for multi-line LLM responses and 
categorized events to aid in debugging and session tracking.
"""

import logging
import os

# The default file where all session logs are written
SESSION_LOG = "session.log"

def setup_logger() -> logging.Logger:
    """
    Configures and returns a logger instance for the application.

    This function sets up a FileHandler that writes to 'session.log' with 
    a custom multi-line separator. It ensures that old logs are cleared on 
    startup if the logger is being re-initialized.

    Returns:
        A configured logging.Logger instance.
    """
    # Cleanup previous session log to ensure a fresh start for every run
    if os.path.exists(SESSION_LOG):
        try:
            os.remove(SESSION_LOG)
        except Exception:
            pass # Ignore if the file is locked

    logger = logging.getLogger("OllamaAgentCoder")
    logger.setLevel(logging.INFO)
    
    # Singleton pattern: Avoid adding multiple handlers if called multiple times
    if not logger.handlers:
        file_handler = logging.FileHandler(SESSION_LOG, encoding="utf-8")
        # Custom format that adds a visible separator between entries
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s\n' + '-'*40,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

# Singleton global logger instance used across the whole project
logger = setup_logger()

def log_to_file(text: str, category: str = "INFO"):
    """
    Records an event or LLM response to the session log.

    Handles both single-line messages and large multi-line blocks (like LLM 
    generated code or diagnostics) by wrapping them in clearly labeled 
    start/end markers.

    Args:
        text: The string or data to be logged.
        category: A label indicating the type of event (e.g., 'ERROR', 'DIAGNOSTIC').
    """
    # Mapping of semantic categories to standard logging levels
    level_map = {
        "INFO": logging.INFO,
        "SYSTEM": logging.INFO,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "DEBUG": logging.DEBUG,
        "CODER_THOUGHT": logging.INFO,
        "MANAGER_PLAN": logging.INFO,
        "DIAGNOSTIC": logging.INFO,
        "PATCH_RESPONSE": logging.INFO,
        "REWRITE_RESPONSE": logging.INFO,
        "CODE_STAGED": logging.INFO,
        "CODE_COMMITTED": logging.INFO,
        "VERIFICATION_FAILURE": logging.ERROR,
        "CONTEXT_SNAPSHOT": logging.INFO,
    }
    
    level = level_map.get(category, logging.INFO)
    
    # Format multi-line blocks for high readability in the log file
    if "\n" in str(text):
        separator = f"\n{'='*20} {category} START {'='*20}\n"
        end_separator = f"\n{'='*20} {category} END {'='*20}"
        logger.log(level, f"{separator}{text}{end_separator}")
    else:
        # Compact format for simple events
        logger.log(level, f"[{category}] {text}")
