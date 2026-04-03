import os
import logging
import getpass
import json
import base64
from pathlib import Path
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Configure logging
logger = logging.getLogger(__name__)

class CredentialsHelper:
    """
    Unified class for managing credentials.
    Supports loading from environment variables, a local vault file (~/.creds.vault),
    and legacy creds.py.
    """
    
    VAULT_FILE = Path.home() / ".creds.vault"
    CREDS_FILE = Path(__file__).parent.parent / "creds.py"
    
    def __init__(self, vault_password: Optional[str] = None, use_vault: bool = True):
        self._credentials: Dict[str, str] = {}
        self._initialized = False
        self._load_all(vault_password, use_vault)

    def _load_all(self, vault_password: Optional[str] = None, use_vault: bool = True):
        """Loads all available credentials into internal cache and environment variables."""
        # 1. Load from legacy creds.py if available
        if self.CREDS_FILE.exists():
            self._load_from_creds_py()
        
        # 2. Load from vault file if available (only if use_vault is True)
        if use_vault and self.VAULT_FILE.exists():
            self._load_from_vault(vault_password)
        
        # 3. Inject all found credentials into environment variables
        self._inject_into_env()
        self._initialized = True

    def _load_from_creds_py(self):
        """Attempts to load credentials from the legacy creds.py file."""
        try:
            import creds
            # Iterate through attributes in creds module
            for attr in dir(creds):
                if not attr.startswith("__") and isinstance(getattr(creds, attr), str):
                    self._credentials[attr] = getattr(creds, attr)
            logger.info("Loaded credentials from legacy creds.py")
        except ImportError:
            logger.debug("creds.py not found, skipping legacy load.")
        except Exception as e:
            logger.error(f"Error loading from creds.py: {e}")

    def _derive_key(self, password: str, salt: bytes = b'salt_') -> bytes:
        """Derives a cryptographic key from a password."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def _load_from_vault(self, password: Optional[str] = None):
        """Decrypts and loads credentials from the local vault file."""
        if not password:
            print(f"\n--- Credentials Vault Found at {self.VAULT_FILE} ---")
            password = getpass.getpass("Enter vault decryption password: ")
        
        try:
            with open(self.VAULT_FILE, "rb") as f:
                data = f.read()
            
            # Simple format: salt(16 bytes) + encrypted_data
            salt = data[:16]
            encrypted_content = data[16:]
            
            key = self._derive_key(password, salt)
            fernet = Fernet(key)
            decrypted_data = fernet.decrypt(encrypted_content)
            
            vault_creds = json.loads(decrypted_data.decode())
            self._credentials.update(vault_creds)
            logger.info(f"Loaded {len(vault_creds)} credentials from vault.")
        except Exception as e:
            logger.error(f"Failed to decrypt vault: {e}")
            print("Error: Invalid vault password or corrupted vault file.")

    def _inject_into_env(self):
        """Injects loaded credentials into os.environ for broad accessibility."""
        # Map certain keys to standard environment variable names if necessary
        mapping = {
            "OPENAI_KEY": "OPENAI_API_KEY",
            "ANTHROPIC_KEY": "ANTHROPIC_API_KEY",
            "GEMINI_KEY": "GOOGLE_API_KEY",
            "TAVILY_SEARCH_KEY": "TAVILY_API_KEY",
            "GROK_KEY": "XAI_API_KEY",
            "GROQ_KEY": "GROQ_API_KEY",
            "DEVICES_SSH_USERNAME": "DEVICES_SSH_USERNAME",
            "DEVICES_SSH_PASSWORD": "DEVICES_SSH_PASSWORD"
        }
        
        for key, value in self._credentials.items():
            # Inject the original key
            os.environ[key] = value
            # Inject the mapped key if it exists
            if key in mapping:
                os.environ[mapping[key]] = value
                
    def get_credential(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieves a credential by key, checking cache, then os.environ."""
        val = self._credentials.get(key) or os.environ.get(key)
        if not val and key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"]:
            # Check common aliases
            aliases = {
                "OPENAI_API_KEY": "OPENAI_KEY",
                "ANTHROPIC_API_KEY": "ANTHROPIC_KEY",
                "GOOGLE_API_KEY": "GEMINI_KEY"
            }
            alias = aliases.get(key)
            if alias:
                val = self._credentials.get(alias) or os.environ.get(alias)
        
        return val or default

    @classmethod
    def create_vault(cls, credentials: Dict[str, str], password: str):
        """Utility to create a new vault file."""
        salt = os.urandom(16)
        helper = cls(vault_password="dummy") # initialized empty
        key = helper._derive_key(password, salt)
        fernet = Fernet(key)
        
        encrypted_data = fernet.encrypt(json.dumps(credentials).encode())
        with open(cls.VAULT_FILE, "wb") as f:
            f.write(salt + encrypted_data)
        print(f"Vault created successfully at {cls.VAULT_FILE}")

# Singleton instance for easy access
_instance: Optional[CredentialsHelper] = None

def get_helper(password: Optional[str] = None, use_vault: bool = True) -> CredentialsHelper:
    global _instance
    if _instance is None:
        _instance = CredentialsHelper(password, use_vault)
    return _instance

def get_credential(key: str, default: Optional[str] = None) -> Optional[str]:
    return get_helper().get_credential(key, default)
