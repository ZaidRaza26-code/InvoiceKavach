"""
Check which Gemini models YOUR key can use.
Run:  python check_key.py YOUR_KEY      (or set GEMINI_API_KEY first)
"""
import os
import sys

key = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("GEMINI_API_KEY", "")).strip().strip("\"'")
if not key:
    sys.exit("Usage: python check_key.py YOUR_KEY")

from google import genai

try:
    client = genai.Client(api_key=key)
    names = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if "generateContent" in actions and "flash" in m.name.lower():
            names.append(m.name.replace("models/", ""))
    print("Key works. Flash models you can use:")
    for n in sorted(names):
        print("  -", n)
    print("\nPut one in .streamlit/secrets.toml as:  GEMINI_MODEL = \"<name>\"")
except Exception as e:
    print("Key check failed:\n", str(e)[:400])
