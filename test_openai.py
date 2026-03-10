#!/usr/bin/env python3
"""Quick test to verify OpenAI API connectivity"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get('OPENAI_API_KEY')
if not API_KEY:
    print("❌ OPENAI_API_KEY not found in .env")
    exit(1)

print("Testing OpenAI API connection...")
try:
    resp = requests.post(
        'https://api.openai.com/v1/chat/completions',
        headers={'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'},
        json={
            'model': 'gpt-4o-mini',
            'messages': [{'role': 'user', 'content': 'Say hello'}],
            'temperature': 0.7,
        },
        timeout=15,
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        print("✅ OpenAI API connection OK!")
        data = resp.json()
        print(f"Response: {data['choices'][0]['message']['content']}")
    else:
        print(f"❌ HTTP {resp.status_code}")
        print(f"Response: {resp.text[:300]}")
except requests.exceptions.ConnectTimeout:
    print("❌ Connection timeout - network/firewall issue?")
except requests.exceptions.Timeout:
    print("❌ Request timeout - API is slow or unreachable")
except requests.exceptions.ConnectionError as e:
    print(f"❌ Connection error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
