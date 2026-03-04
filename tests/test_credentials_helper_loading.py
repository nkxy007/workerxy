import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from utils.credentials_helper import get_helper, get_credential

def test_credentials_loading():
    print("Testing CredentialsHelper loading from legacy creds.py...")
    
    # Ensure creds.py is available for the test
    try:
        import creds
        expected_openai = creds.OPENAI_KEY
        print(f"Legacy OPENAI_KEY: {expected_openai[:10]}...")
    except ImportError:
        print("Error: creds.py not found in the path. Please ensure it exists.")
        return

    # Initialize helper (should load from creds.py automatically)
    helper = get_helper()
    
    # Test get_credential
    openai_key = get_credential("OPENAI_KEY")
    openai_api_key = get_credential("OPENAI_API_KEY")
    
    print(f"Helper OPENAI_KEY: {openai_key[:10] if openai_key else 'None'}...")
    print(f"Helper OPENAI_API_KEY: {openai_api_key[:10] if openai_api_key else 'None'}...")
    
    # Check env var injection
    env_openai = os.environ.get("OPENAI_API_KEY")
    print(f"Environment OPENAI_API_KEY: {env_openai[:10] if env_openai else 'None'}...")
    
    assert openai_key == expected_openai, "OPENAI_KEY mismatch"
    assert openai_api_key == expected_openai, "OPENAI_API_KEY mismatch"
    assert env_openai == expected_openai, "Environment variable injection failed"
    
    print("\nSUCCESS: CredentialsHelper correctly loaded and injected legacy credentials!")

if __name__ == "__main__":
    test_credentials_loading()
