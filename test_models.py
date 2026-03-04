import os
import sys
from pathlib import Path

# Add the project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from utils.credentials_helper import get_credential, get_helper
from anthropic import Anthropic

# Initialize credentials
get_helper()

client = Anthropic(api_key=get_credential("ANTHROPIC_KEY"))
try:
    models = client.models.list()
    print("Available Sonnet Models:")
    for model in models.data:
        if "sonnet" in model.id:
            print(f"- {model.id}")
except Exception as e:
    print(f"Error fetching models: {e}")
