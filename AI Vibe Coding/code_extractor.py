# code_extractor.py
import re

def extract_code_blocks(text: str) -> List[str]:
    pattern = r"```(?:\w+)?\n(.*?)\n```"
    return re.findall(pattern, text, re.DOTALL)
