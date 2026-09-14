"""
Ollama LLM Client wrapper with Universal Tool Calling, multi-strategy parsing
(Qwen tags, Llama, DeepSeek, Mistral, Claude XML, Python-style, ReAct, JSON),
streaming, and model discovery.
"""

import ast
import json
import re
from typing import Any, Dict, Generator, List, Optional
import ollama


def strip_thinking_tags(text: str) -> str:
    """Strip <think>...</think> reasoning blocks emitted by models like DeepSeek-R1 / QwQ."""
    if not text:
        return ""
    # Strip <think>...</think>
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Strip [THINK]...[/THINK]
    cleaned = re.sub(r"\[THINK\].*?\[/THINK\]", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()


def clean_tool_call_text(text: str) -> str:
    """
    Remove raw tool call tags from text so they don't clutter the user terminal UI.
    """
    if not text:
        return ""

    # Remove Qwen <function=...> ... </tool_call> / </function>
    cleaned = re.sub(
        r"<function=[a-zA-Z0-9_\-]+>.*?(?:</function>|</tool_call>|$)",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE
    )

    # Remove <tool_call>...</tool_call> and <function_call>...</function_call>
    cleaned = re.sub(r"<tool_call>.*?</tool_call>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<function_call>.*?</function_call>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<invoke.*?>.*?</invoke>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)

    # Remove loose closing tags if leftover
    cleaned = re.sub(r"</tool_call>|</function>|</function_call>|</invoke>", "", cleaned, flags=re.IGNORECASE)

    # Remove ReAct Action / Action Input blocks if followed by end
    cleaned = re.sub(r"Action:\s*[a-zA-Z0-9_\-]+\s*\nAction Input:\s*\{.*?\}", "", cleaned, flags=re.DOTALL)

    return cleaned.strip()


def extract_json_dicts(text: str) -> List[Dict[str, Any]]:
    """Scan text and extract any valid top-level JSON dictionaries."""
    decoder = json.JSONDecoder()
    pos = 0
    results = []
    while pos < len(text):
        idx = text.find("{", pos)
        if idx == -1:
            break
        try:
            obj, end = decoder.raw_decode(text, idx)
            if isinstance(obj, dict):
                results.append(obj)
            pos = end
        except json.JSONDecodeError:
            pos = idx + 1
    return results


def parse_loose_args(args_val: Any) -> Dict[str, Any]:
    """Ensure tool arguments are parsed into a valid dict."""
    if isinstance(args_val, dict):
        return args_val
    if isinstance(args_val, str):
        cleaned = args_val.strip()
        if not cleaned:
            return {}
        try:
            return json.loads(cleaned)
        except Exception:
            pass
        try:
            val = ast.literal_eval(cleaned)
            if isinstance(val, dict):
                return val
        except Exception:
            pass
        return {"raw": cleaned}
    return {}


def parse_qwen_tool_calls(text: str) -> List[Dict[str, Any]]:
    """
    Parse Qwen XML tool-call format:
    <function=tool_name> <parameter=key1> val1 <parameter=key2> val2 </tool_call>
    or <function=tool_name><parameter=key>val</parameter></function>
    """
    tool_calls = []
    qwen_func_pattern = re.compile(
        r"<function=([a-zA-Z0-9_\-]+)>\s*(.*?)\s*(?:</function>|</tool_call>|$)",
        re.DOTALL | re.IGNORECASE
    )
    param_pattern = re.compile(
        r"<parameter=([a-zA-Z0-9_\-]+)>\s*(.*?)(?=(?:<parameter=|</function>|</tool_call>|$))",
        re.DOTALL | re.IGNORECASE
    )

    for match in qwen_func_pattern.finditer(text):
        func_name = match.group(1).strip()
        body = match.group(2).strip()

        # Extract parameters
        arguments: Dict[str, Any] = {}
        param_matches = list(param_pattern.finditer(body))
        if param_matches:
            for p_match in param_matches:
                p_name = p_match.group(1).strip()
                p_val = p_match.group(2).strip()
                # Clean any closing parameter tag </parameter>
                p_val = re.sub(r"</parameter>$", "", p_val, flags=re.IGNORECASE).strip()
                # Try parsing JSON values (e.g. true, numbers, arrays, strings)
                try:
                    p_val = json.loads(p_val)
                except Exception:
                    pass
                arguments[p_name] = p_val
        elif body:
            # If body has JSON directly inside <function=name>{...}</function>
            try:
                arguments = json.loads(body)
            except Exception:
                arguments = {"raw": body}

        if func_name:
            tool_calls.append({"name": func_name, "arguments": arguments})

    return tool_calls


def parse_xml_invoke_tool_calls(text: str) -> List[Dict[str, Any]]:
    """
    Parse Claude / XML invoke tool-call format:
    <invoke name="tool_name">
      <parameter name="key">value</parameter>
    </invoke>
    """
    tool_calls = []
    invoke_pattern = re.compile(
        r"<invoke\s+name=[\"']([a-zA-Z0-9_\-]+)[\"']\s*>(.*?)</invoke>",
        re.DOTALL | re.IGNORECASE
    )
    param_pattern = re.compile(
        r"<parameter\s+name=[\"']([a-zA-Z0-9_\-]+)[\"']\s*>(.*?)</parameter>",
        re.DOTALL | re.IGNORECASE
    )

    for match in invoke_pattern.finditer(text):
        func_name = match.group(1).strip()
        body = match.group(2).strip()
        arguments: Dict[str, Any] = {}

        for p_match in param_pattern.finditer(body):
            p_name = p_match.group(1).strip()
            p_val = p_match.group(2).strip()
            try:
                p_val = json.loads(p_val)
            except Exception:
                pass
            arguments[p_name] = p_val

        if func_name:
            tool_calls.append({"name": func_name, "arguments": arguments})

    return tool_calls


def parse_tag_wrapped_json(text: str) -> List[Dict[str, Any]]:
    """
    Parse <tool_call>...</tool_call> or <function_call>...</function_call> blocks containing JSON.
    """
    tool_calls = []
    tag_pattern = re.compile(
        r"<(?:tool_call|function_call)>\s*(.*?)\s*</(?:tool_call|function_call)>",
        re.DOTALL | re.IGNORECASE
    )

    for match in tag_pattern.finditer(text):
        block = match.group(1).strip()
        # Try direct JSON parse
        try:
            data = json.loads(block)
            if isinstance(data, dict):
                name = data.get("name") or data.get("tool") or data.get("function") or data.get("call")
                args = data.get("arguments") or data.get("parameters") or data.get("args") or data.get("input") or {}
                if name:
                    tool_calls.append({"name": str(name), "arguments": parse_loose_args(args)})
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("tool") or item.get("function")
                        args = item.get("arguments") or item.get("parameters") or item.get("args") or {}
                        if name:
                            tool_calls.append({"name": str(name), "arguments": parse_loose_args(args)})
        except Exception:
            # Check for inner JSON dicts
            inner_dicts = extract_json_dicts(block)
            for d in inner_dicts:
                name = d.get("name") or d.get("tool") or d.get("function")
                args = d.get("arguments") or d.get("parameters") or d.get("args") or {}
                if name:
                    tool_calls.append({"name": str(name), "arguments": parse_loose_args(args)})

    return tool_calls


def parse_react_action_format(text: str) -> List[Dict[str, Any]]:
    """
    Parse ReAct format:
    Action: tool_name
    Action Input: {"param": "val"}
    """
    tool_calls = []
    react_pattern = re.compile(
        r"Action:\s*([a-zA-Z0-9_\-]+)\s*\nAction Input:\s*(\{.*?\}|\[.*?\]|[^\n]+)",
        re.DOTALL | re.IGNORECASE
    )
    for match in react_pattern.finditer(text):
        name = match.group(1).strip()
        input_str = match.group(2).strip()
        args = parse_loose_args(input_str)
        if name:
            tool_calls.append({"name": name, "arguments": args})
    return tool_calls


class OllamaClient:
    """Wrapper for Ollama API supporting native tool calling, universal fallback extraction, and model discovery."""

    def __init__(self, host: str = "http://127.0.0.1:11434", default_model: str = "qwen2.5-coder:32b"):
        self.host = host
        self.client = ollama.Client(host=host)
        self.default_model = default_model

    def list_models_detailed(self) -> List[Dict[str, Any]]:
        """Fetch list of models with full parameter size, quant, and disk size details."""
        try:
            res = self.client.list()
            models = []
            model_items = res.get("models", []) if isinstance(res, dict) else getattr(res, "models", [])
            for m in model_items:
                name = m.get("name") if isinstance(m, dict) else getattr(m, "model", getattr(m, "name", None))
                if not name:
                    continue

                # Extract size details safely
                size_bytes = m.get("size", 0) if isinstance(m, dict) else getattr(m, "size", 0)
                size_gb = f"{size_bytes / (1024**3):.1f} GB" if size_bytes else "Unknown"

                details = m.get("details", {}) if isinstance(m, dict) else getattr(m, "details", None)
                param_size = details.get("parameter_size", "N/A") if isinstance(details, dict) else getattr(details, "parameter_size", "N/A")
                quant = details.get("quantization_level", "N/A") if isinstance(details, dict) else getattr(details, "quantization_level", "N/A")

                models.append({
                    "name": name,
                    "size_gb": size_gb,
                    "parameter_size": param_size or "N/A",
                    "quantization": quant or "N/A"
                })
            return models
        except Exception:
            return []

    def list_models(self) -> List[str]:
        """Fetch list of model names currently available in local Ollama."""
        detailed = self.list_models_detailed()
        return [m["name"] for m in detailed]

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ):
        """
        Send chat request to Ollama with tools and options (num_ctx, temperature, etc.).
        Returns the chat response dict / object.
        """
        target_model = model or self.default_model
        params: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            params["tools"] = tools
        if options:
            params["options"] = options

        return self.client.chat(**params)

    def extract_tool_calls(self, message: Any) -> List[Dict[str, Any]]:
        """
        Universal tool calling extractor.
        Handles:
        1. Native tool_calls attribute/dict from Ollama / OpenAI
        2. Qwen XML/tag syntax: <function=name> <parameter=key> val </tool_call>
        3. <tool_call> / <function_call> tag-wrapped JSON
        4. Claude XML <invoke name="..."> ... </invoke>
        5. ReAct Action: ... / Action Input: ...
        6. Markdown ```json code fences and loose inline JSON dictionaries
        """
        tool_calls: List[Dict[str, Any]] = []

        # 1. Native tool_calls attribute/key
        raw_calls = None
        if isinstance(message, dict):
            raw_calls = message.get("tool_calls")
        else:
            raw_calls = getattr(message, "tool_calls", None)

        if raw_calls:
            for call in raw_calls:
                func_obj = call.get("function") if isinstance(call, dict) else getattr(call, "function", None)
                if func_obj:
                    name = func_obj.get("name") if isinstance(func_obj, dict) else getattr(func_obj, "name", "")
                    args = func_obj.get("arguments") if isinstance(func_obj, dict) else getattr(func_obj, "arguments", {})
                    tool_calls.append({"name": name, "arguments": parse_loose_args(args)})
            if tool_calls:
                return tool_calls

        # Extract content text
        content = ""
        if isinstance(message, dict):
            content = message.get("content", "")
        else:
            content = getattr(message, "content", "")

        if not content or not isinstance(content, str):
            return []

        # Strip reasoning thoughts if present (DeepSeek-R1 / QwQ)
        eval_content = strip_thinking_tags(content)

        # 2. Check for Qwen tag format: <function=name> <parameter=key> val </tool_call>
        qwen_calls = parse_qwen_tool_calls(eval_content)
        if qwen_calls:
            return qwen_calls

        # 3. Check for tag-wrapped JSON: <tool_call> ... </tool_call>
        tag_calls = parse_tag_wrapped_json(eval_content)
        if tag_calls:
            return tag_calls

        # 4. Check for Claude XML invoke: <invoke name="..."> ... </invoke>
        xml_calls = parse_xml_invoke_tool_calls(eval_content)
        if xml_calls:
            return xml_calls

        # 5. Check for ReAct Action / Action Input format
        react_calls = parse_react_action_format(eval_content)
        if react_calls:
            return react_calls

        # 6. Fallback: Parse markdown JSON code fences or raw JSON dicts
        # Check ```json ... ``` blocks first
        json_fence_matches = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", eval_content, flags=re.DOTALL)
        for fence_content in json_fence_matches:
            try:
                parsed = json.loads(fence_content)
                if isinstance(parsed, dict):
                    name = parsed.get("name") or parsed.get("tool") or parsed.get("function")
                    args = parsed.get("arguments") or parsed.get("parameters") or parsed.get("args") or {}
                    if name:
                        tool_calls.append({"name": str(name), "arguments": parse_loose_args(args)})
            except Exception:
                pass

        if tool_calls:
            return tool_calls

        # General loose JSON dicts scan
        dicts = extract_json_dicts(eval_content)
        for d in dicts:
            name = d.get("name") or d.get("tool") or d.get("function") or d.get("call")
            if name and isinstance(name, str):
                args = d.get("arguments") or d.get("parameters") or d.get("args") or d.get("input") or {}
                tool_calls.append({"name": name, "arguments": parse_loose_args(args)})

        return tool_calls
