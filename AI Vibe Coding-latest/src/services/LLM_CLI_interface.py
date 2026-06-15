import re
import ast
from pathlib import Path
from typing import List, Dict, Any
from src.services.base import BaseService
from code_extractor import extract_code_blocks
from communication_lessons.learning_from_mistakes import LearningFromMistakes

class LLM_CLI_Interface(BaseService):
    """
    Heuristic-based observer that interprets LLM natural language recommendations.

    Uses a combination of regex patterns, project context (known files), 
    and 'learned' patterns from historical interactions to detect intent 
    (saving files or running commands) without requiring strict formatting.
    """

    def __init__(self, orchestrator=None, console=None):
        """
        Initializes the interface with a learner and predefined CLI questions.

        Args:
            orchestrator: The orchestrator instance.
            console: The rich console instance.
        """
        super().__init__(orchestrator)
        self.console = console
        self.learner = LearningFromMistakes()
        self.learned_patterns = [] # Dynamic cache for filename detection regex
        self._refresh_learned_patterns()
        self.cli_questions = {
            "confirm_code": "I see a code block. Should I save it? If so, what filename?",
            "rewrite_code": "I couldn't clearly identify the filename or action for that code. Can you please provide the code in a single block and clearly state the filename (e.g., 'Save this to filename.py')?",
            "debug": "I detected a syntax error in the code you provided: {error}. Please revise it.",
            "confirm_run": "You mentioned a command: '{command}'. Should I execute it?",
            "no_action": "I'm not sure how to proceed with that response. Could you please specify a file to save or a command to run?"
        }

    def get_adaptive_prompt(self, key: str, **kwargs) -> str:
        """
        Retrieves a learned prompt from history or falls back to a static one.

        Args:
            key (str): The prompt identifier (e.g., 'debug', 'no_action').
            **kwargs: Replacement values for the prompt template.

        Returns:
            str: The final prompt string.
        """
        # 1. Try to find a 'Catalyst' prompt from history
        effectiveness = self.learner.analyze_prompt_effectiveness()
        catalysts = effectiveness.get("catalysts", [])
        
        # Categorization logic: find catalysts that match the intent of the key
        intent_keywords = {
            "debug": ["error", "syntax", "fail", "Traceback"],
            "no_action": ["how to proceed", "specify", "clarify"],
            "rewrite_code": ["rewrite", "modular", "single block"]
        }
        
        keywords = intent_keywords.get(key, [])
        for catalyst in catalysts:
            if any(kw in catalyst for kw in keywords):
                # Use the learned successful prompt
                return catalyst

        # 2. Fallback to static prompt
        template = self.cli_questions.get(key, "I'm not sure how to proceed.")
        return template.format(**kwargs)

    def _refresh_learned_patterns(self):
        """Loads learned filename detection patterns from history."""
        # 1. Load exact filename headers from past successes
        lessons = self.learner.interpreting_LLM_output()
        for lesson in lessons:
            if lesson.get("possible_filename"):
                fname = lesson["possible_filename"][0]
                self.learned_patterns.append(re.escape(fname) + r"\s*[:\n\-]*")
        
        # 2. Load generalized prefix patterns from history
        new_heuristics = self.learner.generate_new_heuristics()
        self.learned_patterns.extend(new_heuristics)
        
        # Deduplicate while preserving order
        self.learned_patterns = list(dict.fromkeys(self.learned_patterns))

    def llm_output_processor(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Analyzes LLM output text to identify intended actions.

        This method processes code blocks, shell commands, and rename 
        instructions, applying syntax checks and heuristic detection.
        """
        actions = []
        
        # 0. Check for Support Mode (Conversational drift)
        if self._detect_support_mode(response_text):
            actions.append({"action": "support_mode_detected"})

        # 1. Check for Rename Instructions
        rename_actions = self._detect_renames(response_text)
        actions.extend(rename_actions)

        code_blocks = extract_code_blocks(response_text)
        
        # Split text into segments around code blocks
        text_segments = re.split(r"```\w*[\s\n]+.*?```", response_text, flags=re.DOTALL)
        if len(text_segments) == 1 and code_blocks:
            text_segments = [response_text]

        # Context Awareness: Get the last file mentioned in the conversation
        last_failed_file = self._get_last_failed_file()

        # 2. Process Code Blocks
        for i, (lang, code) in enumerate(code_blocks):
            search_text = ""
            if i < len(text_segments):
                search_text += text_segments[i]
            if i + 1 < len(text_segments):
                search_text += text_segments[i+1]

            filename = self._detect_filename(search_text, code, lang)
            
            # Context-Aware Fallback: If no filename detected, check if we just sent a debug prompt
            if not filename and last_failed_file:
                if len(code_blocks) == 1:
                    filename = last_failed_file
                    self.console.print(f"[cyan]Context Match: Assuming code block is for {filename}[/cyan]")

            if not filename:
                filename = self._learn_from_history(search_text, code)

            # Heuristic: Check if it's a snippet vs a full block
            is_snippet = "..." in code or "# rest of" in code.lower()
            if is_snippet:
                self.console.print(f"[yellow]Warning: Block {i+1} appears to be a snippet.[/yellow]")
                if filename:
                    actions.append({
                        "action": "needs_manual_completion",
                        "filename": filename
                    })
                    continue # Skip saving

            # Syntax Check for Python
            if filename and filename.endswith(".py"):
                syntax_error = self._check_syntax(code)
                if syntax_error:
                    message = self.get_adaptive_prompt("debug", error=syntax_error)
                    actions.append({
                        "action": "feedback_required",
                        "message": message
                    })
                    continue

            if filename:
                actions.append({
                    "action": "save",
                    "filename": filename,
                    "content": code,
                    "confidence": "high",
                    "is_snippet": is_snippet,
                    "language": lang
                })
            else:
                actions.append({
                    "action": "needs_confirmation",
                    "type": "save",
                    "content": code,
                    "message": self.get_adaptive_prompt("confirm_code")
                })

        # 3. Process Shell Commands
        all_conv_text = " ".join(text_segments)
        commands = self._detect_commands(all_conv_text)
        for cmd in commands:
            learned_data = self.learner.select_best_llm_prompts()
            timeout_prompts = learned_data.get("timeout_risk_prompts", [])
            is_risky = any(cmd in p for p in timeout_prompts)
            
            msg = self.cli_questions["confirm_run"].format(command=cmd)
            if is_risky:
                msg = f"[bold red]WARNING: Similar commands have timed out in the past.[/bold red]\n{msg}"

            actions.append({
                "action": "needs_confirmation",
                "type": "run_shell",
                "command": cmd,
                "message": msg
            })

        # 4. Final Fallback
        if code_blocks and not any(a['action'] in ['save', 'needs_confirmation'] for a in actions):
            actions.append({
                "action": "feedback_required",
                "message": self.get_adaptive_prompt("no_action")
            })

        return actions

    def _detect_renames(self, text: str) -> List[Dict[str, Any]]:
        """
        Identifies 'rename' or 'move' instructions in the LLM text.
        
        Matches patterns like:
        - "Rename space invaders.py to spaceinvaders.py"
        - "Corrected filename: spaceinvaders.py" (compared against existing files)
        """
        actions = []
        # Pattern 1: Explicit Rename
        rename_patterns = [
            r"rename\s+([\w\s\./-]+\.\w+)\s+to\s+([\w\./-]+\.\w+)",
            r"move\s+([\w\s\./-]+\.\w+)\s+to\s+([\w\./-]+\.\w+)"
        ]
        
        for pattern in rename_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for old, new in matches:
                actions.append({
                    "action": "rename",
                    "old_name": old.strip(),
                    "new_name": new.strip(),
                    "message": f"Rename '{old}' to '{new}'?"
                })

        # Pattern 2: Corrected Filename Lists
        # If the LLM lists a filename that is a variant of an existing file
        tree = self.orchestrator.code_management.get_tree()
        known_files = set(re.findall(r"[\w\s\./-]+\.\w+", tree))
        
        potential_new_files = re.findall(r"(?:•|\*|\-)\s*([\w\./-]+\.\w+)", text)
        for new_file in potential_new_files:
            # If the new file is NOT in the tree, but a very similar one IS
            if new_file not in known_files:
                for known in known_files:
                    # If the only difference is a space or case
                    if known.replace(" ", "").lower() == new_file.lower():
                        actions.append({
                            "action": "rename",
                            "old_name": known,
                            "new_name": new_file,
                            "message": f"Rename '{known}' to '{new_file}' (fixes space/naming error)?"
                        })

        return actions

    def _get_last_failed_file(self) -> str:
        """
        Scans conversation history to find the most recent file that failed a syntax or run check.
        """
        if not self.orchestrator or not self.orchestrator.messages:
            return None
            
        # Search backwards through messages
        for msg in reversed(self.orchestrator.messages):
            if msg["role"] == "user":
                # Look for "I detected a syntax error in..." or similar prompts
                match = re.search(r"code you provided for ([\w\./-]+\.\w+):", msg["content"])
                if match: return match.group(1)
                
                # Broad search for filenames in the last user prompt if it contained "error"
                if "error" in msg["content"].lower():
                    potential = re.findall(r"([\w\./-]+\.\w+)", msg["content"])
                    if potential: return potential[0]
                    
        return None

    def _detect_support_mode(self, text: str) -> bool:
        """
        Detects if the LLM has entered 'Support Mode' (conversational GUI advice).

        Args:
            text (str): The LLM response text.

        Returns:
            bool: True if support mode detected, False otherwise.
        """
        keywords = [
            "right-click", "paste into", "open your ide", "visual studio code",
            "pycharm", "text editor", "ctrl+s", "cmd+s", "save the file manually",
            "file menu", "navigate to the project directory"
        ]
        text_lower = text.lower()
        matches = [kw for kw in keywords if kw in text_lower]
        return len(matches) >= 2 # Require at least 2 keywords to reduce false positives

    def _detect_filename(self, text: str, code: str, lang: str = None) -> str:
        """
        Attempts to detect a filename from the surrounding text of a code block.

        Args:
            text (str): The text surrounding the code block.
            code (str): The content of the code block.
            lang (str, optional): The language tag from the code block.

        Returns:
            str: The detected filename, or None.
        """
        # 0. Check Learned Patterns First
        for pattern in self.learned_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Extract filename from the matched pattern if possible, or use the pattern string itself
                potential = re.findall(r"([\w\./-]+\.\w+)", match.group(0))
                if potential: return potential[0]

        patterns = [
            r"(?:save|write|create|to|into|in|file|named)\s+([\w\./-]+\.\w+)",
            r"filename:\s*([\w\./-]+\.\w+)",
            r"##\s+([\w\./-]+\.\w+)",
            r"([\w\./-]+\.\w+):",
            r"(?:^|\n)([\w\./-]+\.\w+)\s*\n" # Matches filename on a single line above the block
        ]
        
        valid_extensions = {'.py', '.js', '.ts', '.html', '.css', '.md', '.json', '.txt', '.yaml', '.yml'}
        
        # Map language tags to extensions
        lang_map = {
            'python': '.py', 'javascript': '.js', 'typescript': '.ts',
            'html': '.html', 'css': '.css', 'markdown': '.md', 'json': '.json'
        }
        
        tree = self.orchestrator.code_management.get_tree()
        known_files = set(re.findall(r"[\w\./-]+\.\w+", tree))
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                ext = Path(match).suffix.lower()
                if ext in valid_extensions or match in known_files:
                    return match
        
        # Language tag fallback
        if lang and lang in lang_map:
            target_ext = lang_map[lang]
            for file in known_files:
                if file.endswith(target_ext) and file in text:
                    return file

        for file in sorted(list(known_files), key=len, reverse=True):
            if file in text:
                return file
                
        return None

    def _learn_from_history(self, text: str, code: str) -> str:
        """
        Attempts to find a filename by matching against previously failed patterns.

        Args:
            text (str): The text surrounding the code block.
            code (str): The content of the code block.

        Returns:
            str: A filename learned from history, or None.
        """
        past_intents = self.learner.interpreting_LLM_output()
        for pattern in past_intents:
            # Simple similarity: if a significant part of the current response matches a past failure
            if pattern['response_snippet'][:50] in text and pattern.get('possible_filename'):
                return pattern['possible_filename'][0]
        return None

    def _aggressive_detect(self, text: str) -> str:
        """
        Looks for ANY string that looks like a filename/path as a last resort.

        Args:
            text (str): The text to search.

        Returns:
            str: The first path-like string found, or None.
        """
        potential = re.findall(r"([\w\./-]+\.\w+)", text)
        for p in potential:
            if '.' in p and len(p.split('.')[-1]) <= 4:
                return p
        return None

    def _detect_commands(self, text: str) -> List[str]:
        """
        Detects shell commands mentioned in the text (e.g., in backticks).

        Args:
            text (str): The text to search.

        Returns:
            List[str]: A list of detected commands.
        """
        commands = []
        cli_patterns = [
            r"`(pip\s+install\s+[\w-]+)`",
            r"`(python\s+[\w\./-]+\.py)`",
            r"`(ls|dir|mkdir|rm|cp|mv)\s+[^`]+`",
            r"run the command\s+`([^`]+)`",
            r"execute:\s+`([^`]+)`"
        ]
        
        for pattern in cli_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            commands.extend(matches)
            
        return list(set(commands))

    def _check_syntax(self, code: str) -> str:
        """
        Checks the syntax of a Python code block using the AST module.

        Args:
            code (str): The Python code to check.

        Returns:
            str: An error message if syntax is invalid, otherwise None.
        """
        try:
            ast.parse(code)
            return None
        except SyntaxError as e:
            return f"SyntaxError: {e.msg} at line {e.lineno}"
        except Exception as e:
            return str(e)
