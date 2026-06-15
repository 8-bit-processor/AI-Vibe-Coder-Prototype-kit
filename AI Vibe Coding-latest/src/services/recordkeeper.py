import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from src.services.base import BaseService

class Recordkeeper(BaseService):
    """
    Service responsible for logging interactions between the user and the LLM.

    Saves prompts, responses, and identified actions into JSON files within 
    a history directory. This data is used by the learning system.
    """
    def __init__(self, orchestrator=None, history_dir="history"):
        """
        Initializes the recordkeeper and ensures the history directory exists.

        Args:
            orchestrator: The orchestrator instance.
            history_dir (str): The name of the directory to store logs.
        """
        super().__init__(orchestrator)
        self.history_dir = Path(history_dir)
        # Use absolute path to avoid directory issues
        self.history_dir = Path(__file__).parent.parent.parent / history_dir
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def log_interaction(self, prompt: str, response: str, actions: List[Dict[str, Any]]):
        """
        Persists a single interaction to a JSON log file.

        Args:
            prompt (str): The user prompt.
            response (str): The LLM response.
            actions (List[Dict[str, Any]]): The actions identified from the response.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.history_dir / f"log_{timestamp}.json"
        data = {
            "timestamp": timestamp,
            "prompt": prompt,
            "response": response,
            "actions": actions
        }
        with open(log_file, 'w') as f:
            json.dump(data, f, indent=2)
