#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Normalizer wrapper for Ark-like chat completion API.

This module provides a small client that sends the user input to the remote
chat completion endpoint and returns the assistant's content as the
normalized text.

Usage:
    from ai_normalizer import ArkNormalizer
    normalizer = ArkNormalizer(api_key='...', model='doubao-lite-32k-240828')
    normalized = normalizer.normalize('some messy input')

Configuration:
    You can set environment variable `ARK_API_KEY` and optionally `ARK_API_URL`.
"""
import os
import json
import requests
from typing import Optional


class ArkNormalizer:
    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None, model: str = 'doubao-lite-32k-240828', timeout: int = 15):
        self.api_key = api_key or os.environ.get('ARK_API_KEY')
        # default endpoint from user's example
        self.api_url = api_url or os.environ.get('ARK_API_URL') or 'https://ark.cn-beijing.volces.com/api/v3/chat/completions'
        self.model = model
        self.timeout = timeout

    def normalize(self, text: str) -> str:
        """Send `text` to the remote model and return the assistant reply as normalized text.

        If any network or parsing error occurs, returns the original `text` as fallback.
        """
        if not text:
            return text
        if not self.api_key:
            return text

        # Ask the model to return a JSON object: {"normalized": "..."}
        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': '你是一个文本规范化助手。只返回一个 JSON 对象，格式为 {"normalized":"..."}，不要返回任何其它文字或解释。'},
                {'role': 'user', 'content': text}
            ]
        }

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

        try:
            resp = requests.post(self.api_url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            # Try common response shapes: choices[0].message.content
            if isinstance(data, dict):
                # Prefer new-style structure choices[0].message.content
                if 'choices' in data and isinstance(data['choices'], list) and len(data['choices']) > 0:
                    c0 = data['choices'][0]
                    content = None
                    if isinstance(c0, dict) and 'message' in c0 and isinstance(c0['message'], dict) and 'content' in c0['message']:
                        content = c0['message']['content']
                    elif isinstance(c0, dict) and 'content' in c0:
                        content = c0['content']
                    if content:
                        text_out = str(content).strip()
                        # strip fenced code block if present
                        if text_out.startswith('```'):
                            parts = text_out.split('```')
                            if len(parts) >= 2:
                                text_out = parts[1].strip()
                        # try parse JSON
                        try:
                            obj = json.loads(text_out)
                            if isinstance(obj, dict) and 'normalized' in obj:
                                return str(obj['normalized']).strip()
                        except Exception:
                            # not JSON, fall back to raw text
                            return text_out

                # some providers use 'result' or 'data'
                if 'result' in data and isinstance(data['result'], str):
                    return data['result'].strip()
                if 'data' in data and isinstance(data['data'], list) and len(data['data']) > 0:
                    first = data['data'][0]
                    if isinstance(first, dict) and 'content' in first:
                        return first['content'].strip()
            # fallback to textual body
            return resp.text.strip()
        except Exception:
            return text


__all__ = ['ArkNormalizer']

def detect_intent_via_ark(api_key: str, user_input: str, intents: dict, api_url: Optional[str] = None, model: str = 'doubao-lite-32k-240828', timeout: int = 15) -> str:
    """Use Ark chat completion to classify the user_input into one of the provided intents.

    - `intents` is a dict mapping intent name -> list of pattern strings (examples).
    - Returns the chosen intent name or 'FALLBACK'.
    """
    if not api_key:
        return 'FALLBACK'
    api_url = api_url or os.environ.get('ARK_API_URL') or 'https://ark.cn-beijing.volces.com/api/v3/chat/completions'

    # Build a concise prompt asking for the single intent name
    examples_text = []
    for name, patterns in intents.items():
        # include up to a few example patterns to help the model
        sample = patterns[:6]
        examples_text.append(f"- {name}: {sample}")

    user_msg = (
        f"User Input: {user_input}\n"
        f"Available intents (name: examples):\n" + "\n".join(examples_text) + "\n"
        "Please reply with ONLY the single intent name that best matches the User Input, or FALLBACK if none."
    )

    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': 'You are an intent classification assistant. Reply with the single intent name only.'},
            {'role': 'user', 'content': user_msg}
        ]
    }
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and 'choices' in data and isinstance(data['choices'], list) and len(data['choices']) > 0:
            c0 = data['choices'][0]
            if isinstance(c0, dict) and 'message' in c0 and isinstance(c0['message'], dict) and 'content' in c0['message']:
                text = c0['message']['content'].strip()
            elif isinstance(c0, dict) and 'content' in c0:
                text = str(c0['content']).strip()
            else:
                text = ''
            # tokenise and find known intent
            for token in [t.strip() for t in text.replace('\n', ' ').replace(',', ' ').split(' ')]:
                if token in intents:
                    return token
            # otherwise if the whole text equals an intent
            if text in intents:
                return text
            return 'FALLBACK'
        return 'FALLBACK'
    except Exception:
        return 'FALLBACK'
