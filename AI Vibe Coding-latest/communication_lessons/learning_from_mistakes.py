"""
Module: learning_from_mistakes.py
Description: This module implements a 'Self-Learning' heuristic for the CLI Facade.
             It analyzes JSON interaction logs in the 'history/' directory to identify 
             patterns of failure and success. 

The two primary goals of this module are:
1. Error Correction Learning: Identify which prompts effectively got the LLM to fix specific code errors.
2. Intent Detection Learning: Identify cases where the automated filename detection failed,
   allowing developers to refine heuristics or the system to learn through similarity.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any

class LearningFromMistakes:
    """
    Core engine for analyzing interaction history to improve future performance.
    It treats historical logs as a dataset for 'learning' better prompting and detection strategies.
    """

    def __init__(self, history_dir: Path = None):
        """
        Initializes the learner with a directory containing historical log files.
        
        Args:
            history_dir (Path, optional): Path to the history directory. 
                                        Defaults to '../history' relative to this file.
        """
        if history_dir is None:
            # Heuristic: Assume 'history' is a sibling to the parent folder of this module
            self.history_dir = Path(__file__).parent.parent / "history"
        else:
            self.history_dir = history_dir

    def select_best_llm_prompts(self) -> Dict[str, Any]:
        """
        Analyzes consecutive log entries to find 'Recovery Patterns' and prompt effectiveness.
        
        Returns:
            Dict[str, Any]: A dictionary containing learned patterns:
                           - 'recovery_prompts': Prompts that fixed specific errors.
                           - 'timeout_risk_prompts': Prompts associated with command timeouts.
                           - 'full_block_prompts': Prompts that effectively triggered full code blocks.
        """
        if not self.history_dir.exists():
            return {}

        lessons = {
            "recovery_prompts": {},
            "timeout_risk_prompts": [],
            "full_block_prompts": []
        }
        logs = sorted(self.history_dir.glob("log_*.json"))
        
        for i in range(len(logs) - 1):
            try:
                with open(logs[i], 'r', encoding='utf-8') as f:
                    current = json.load(f)
                with open(logs[i+1], 'r', encoding='utf-8') as f:
                    next_log = json.load(f)
                
                prompt = current.get('prompt', '')
                
                # 1. Error Recovery Patterns
                if any(kw in prompt for kw in ["error", "failed", "Traceback", "Exception"]):
                    next_actions = next_log.get('actions', [])
                    has_fix = any(a.get('action') in ['save', 'run_success'] for a in next_actions)
                    
                    if has_fix:
                        error_type = "General Error"
                        if "ModuleNotFoundError" in prompt: error_type = "Missing Dependency"
                        elif "SyntaxError" in prompt: error_type = "Syntax Error"
                        
                        lessons["recovery_prompts"][error_type] = prompt

                # 2. Timeout Tracking
                current_actions = current.get('actions', [])
                if any("Timeout reached" in str(a.get('stdout', '')) for a in current_actions):
                    lessons["timeout_risk_prompts"].append(prompt)

                # 3. Full Block vs Snippet Success
                next_response = next_log.get('response', '')
                if self._is_full_block(next_response) and len(next_response) > 500:
                    lessons["full_block_prompts"].append(prompt)
                        
            except (json.JSONDecodeError, KeyError, PermissionError):
                continue
                
        return lessons

    def analyze_prompt_effectiveness(self) -> Dict[str, Any]:
        """
        Analyzes historical logs to score prompt effectiveness.
        
        Identifies:
        - Catalyst Prompts: Lead immediately to success (save/run).
        - Dead-End Prompts: Lead to repeated errors or no action.
        
        Returns:
            Dict[str, Any]: Categorized prompts with their effectiveness scores.
        """
        if not self.history_dir.exists():
            return {}

        prompt_stats = {}
        logs = sorted(self.history_dir.glob("log_*.json"))

        for i in range(len(logs) - 1):
            try:
                with open(logs[i], 'r', encoding='utf-8') as f:
                    current = json.load(f)
                with open(logs[i+1], 'r', encoding='utf-8') as f:
                    next_log = json.load(f)

                prompt = current.get('prompt', '')
                if not prompt: continue

                # Heuristic for success: next turn has a 'save' or 'run_success'
                next_actions = next_log.get('actions', [])
                is_success = any(a.get('action') in ['save', 'run_success'] for a in next_actions)
                
                if prompt not in prompt_stats:
                    prompt_stats[prompt] = {"success": 0, "fail": 0, "total": 0}
                
                prompt_stats[prompt]["total"] += 1
                if is_success:
                    prompt_stats[prompt]["success"] += 1
                else:
                    prompt_stats[prompt]["fail"] += 1

            except Exception:
                continue

        # Categorize
        catalysts = []
        dead_ends = []
        for prompt, stats in prompt_stats.items():
            success_rate = stats["success"] / stats["total"]
            if success_rate > 0.7 and stats["total"] >= 1:
                catalysts.append(prompt)
            elif success_rate < 0.3 and stats["total"] >= 1:
                dead_ends.append(prompt)

        return {
            "catalysts": catalysts,
            "dead_ends": dead_ends,
            "all_stats": prompt_stats
        }

    def _is_full_block(self, text: str) -> bool:
        """Heuristic to determine if a code block is a full file or a snippet."""
        # Full blocks usually have imports and don't have ellipsis
        has_imports = any(kw in text for kw in ["import ", "from ", "require(", "import {"])
        has_ellipsis = "..." in text or "# rest of" in text.lower() or "// ..." in text
        return has_imports and not has_ellipsis

    def generate_new_heuristics(self) -> List[str]:
        """
        Analyzes historical logs to identify common strings that precede code blocks.
        
        This allows the system to 'learn' that if an LLM frequently writes 
        'File: main.py' before a code block, then 'File: ' is a strong 
        heuristic for filename detection.
        
        Returns:
            List[str]: A list of suggested regex patterns for filename detection.
        """
        if not self.history_dir.exists():
            return []

        header_counts = {}
        logs = sorted(self.history_dir.glob("log_*.json"))

        for log_path in logs:
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    log = json.load(f)
                
                response = log.get('response', '')
                actions = log.get('actions', [])
                
                for action in actions:
                    if action.get('action') == 'save' and action.get('filename'):
                        filename = action['filename']
                        # Find where this filename appears in the response
                        # and look at the 20 characters before it
                        pattern = re.escape(filename)
                        match = re.search(pattern, response)
                        if match and match.start() > 0:
                            start = max(0, match.start() - 20)
                            header = response[start:match.start()].strip()
                            # Clean up the header to find a potential prefix
                            # e.g., "The code for main.py" -> "The code for "
                            if header:
                                header_counts[header] = header_counts.get(header, 0) + 1
            except Exception:
                continue

        # Filter for patterns that appear multiple times
        suggested = []
        for header, count in header_counts.items():
            if count >= 2:
                # Convert the header into a flexible regex pattern
                # e.g., "File: " -> r"File:\s*([\w\./-]+\.\w+)"
                clean_header = re.escape(header)
                suggested.append(clean_header + r"\s*([\w\./-]+\.\w+)")
                
        return suggested

    def interpreting_LLM_output(self) -> List[Dict[str, Any]]:
        """
        Identifies 'Detection Blind Spots' and categorizes code blocks found in history.
        
        Returns:
            List[Dict[str, Any]]: A list of 'Intent Patterns' including missed filenames
                                 and code block classifications.
        """
        if not self.history_dir.exists():
            return []

        patterns = []
        logs = sorted(self.history_dir.glob("log_*.json"))

        for log_path in logs:
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    log = json.load(f)
                
                actions = log.get('actions', [])
                response = log.get('response', '')
                
                # Check for filename detection failures
                for action in actions:
                    if action.get('action') == 'feedback_required' and "identify the filename" in action.get('message', ''):
                        patterns.append({
                            "response_snippet": response[:300].replace('\n', ' '),
                            "issue": "Filename detection failed",
                            "possible_filename": re.findall(r"[\w\./-]+\.\w+", response),
                            "is_snippet": not self._is_full_block(response)
                        })
            except (json.JSONDecodeError, KeyError):
                continue
                
        return patterns

# Helper functions for quick access without manual class instantiation

def select_best_llm_prompts():
    """Wrapper function to instantiate LearningFromMistakes and return prompt lessons."""
    learner = LearningFromMistakes()
    return learner.select_best_llm_prompts()

def interpreting_LLM_output():
    """Wrapper function to instantiate LearningFromMistakes and return intent patterns."""
    learner = LearningFromMistakes()
    return learner.interpreting_LLM_output()

if __name__ == "__main__":
    """
    Self-test execution: When run directly, this module prints a summary of 
    what it has 'learned' from the local history directory.
    """
    print("==========================================")
    print("   Learning from Mistakes - Analytics")
    print("==========================================\n")
    
    learner = LearningFromMistakes()
    
    # 1. Analyze successful error corrections
    learned_data = learner.select_best_llm_prompts()
    recovery = learned_data.get("recovery_prompts", {})
    print(f"[+] Found {len(recovery)} recovery patterns:")
    if not recovery:
        print("    No recovery patterns identified yet.")
    for err, prompt in recovery.items():
        # Truncate prompt for cleaner terminal output
        clean_prompt = str(prompt)[:70].replace('\n', ' ').strip()
        print(f"    - {err:20}: '{clean_prompt}...'")
    
    # 2. Analyze timeout risks
    timeouts = learned_data.get("timeout_risk_prompts", [])
    print(f"\n[+] Identified {len(timeouts)} risky prompt/command patterns (potential timeouts).")

    # 3. Analyze detection failures
    intents = learner.interpreting_LLM_output()
    print(f"\n[+] Found {len(intents)} cases where intent detection could be improved:")
    if not intents:
        print("    No detection blind spots identified yet.")
    for item in intents[:5]: # Only show the most recent 5 for brevity
        print(f"    - {item['issue']}: {item['response_snippet'][:85]}...")
    
    if len(intents) > 5:
        print(f"    ... and {len(intents) - 5} more.")
