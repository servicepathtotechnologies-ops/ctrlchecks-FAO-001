"""
JSON validation and correction utilities
"""

import json
import re
import logging
from typing import Any, Tuple

logger = logging.getLogger(__name__)


def validate_and_fix_json(text: str, max_attempts: int = 3) -> Tuple[Any, bool]:
    """
    Validate JSON and attempt to fix common issues
    
    Returns:
        Tuple of (parsed_json, is_valid)
    """
    # Try direct parse first
    try:
        parsed = json.loads(text)
        return parsed, True
    except json.JSONDecodeError:
        pass
    
    # Attempt fixes
    fixed_text = text
    
    # Fix 1: Remove markdown code blocks
    fixed_text = re.sub(r'```json\s*\n?', '', fixed_text)
    fixed_text = re.sub(r'```\s*\n?', '', fixed_text)
    
    # Fix 2: Extract JSON from text
    json_match = re.search(r'\{.*\}', fixed_text, re.DOTALL)
    if json_match:
        fixed_text = json_match.group(0)
    
    # Fix 3: Fix common JSON issues
    # Remove trailing commas
    fixed_text = re.sub(r',\s*}', '}', fixed_text)
    fixed_text = re.sub(r',\s*]', ']', fixed_text)
    
    # Fix unquoted keys
    fixed_text = re.sub(r'(\w+):', r'"\1":', fixed_text)
    
    # Try parsing again
    try:
        parsed = json.loads(fixed_text)
        logger.info("JSON fixed successfully")
        return parsed, True
    except json.JSONDecodeError as e:
        logger.warning(f"JSON fix failed: {e}")
        return None, False


def extract_json_from_text(text: str) -> Tuple[Any, bool]:
    """
    Extract JSON object from text that may contain other content
    """
    # Try to find JSON object boundaries
    brace_count = 0
    start_idx = -1
    
    for i, char in enumerate(text):
        if char == '{':
            if start_idx == -1:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx != -1:
                json_str = text[start_idx:i+1]
                parsed, is_valid = validate_and_fix_json(json_str)
                if is_valid:
                    return parsed, True
                start_idx = -1
    
    return None, False


def ensure_json_response(text: str, correction_prompt: str | None = None) -> str:
    """
    Ensure response is valid JSON, add correction prompt if needed
    """
    parsed, is_valid = validate_and_fix_json(text)
    
    if is_valid:
        return text
    
    # Try extraction
    parsed, is_valid = extract_json_from_text(text)
    if is_valid:
        return json.dumps(parsed)
    
    # If still invalid and correction prompt provided, return it
    if correction_prompt:
        return correction_prompt
    
    # Last resort: wrap in JSON
    return json.dumps({"error": "Invalid JSON response", "raw": text[:500]})
