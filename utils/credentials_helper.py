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
    
    # Defaults for HashiCorp Vault
    DEFAULT_HC_MOUNT = "secret"
    DEFAULT_HC_PATH = "workerxy"
    
    def __init__(self, vault_password: Optional[str] = None, use_vault: bool = True, use_hashicorp: bool = False):
        self._credentials: Dict[str, str] = {}
        self._initialized = False
        self._load_all(vault_password, use_vault, use_hashicorp)

    def _load_all(self, vault_password: Optional[str] = None, use_vault: bool = True, use_hashicorp: bool = False):
        """Loads all available credentials into internal cache and environment variables."""
        # 1. Load from legacy creds.py if available
        if self.CREDS_FILE.exists():
            self._load_from_creds_py()
        
        # 2. Load from local vault file if available (only if use_vault is True)
        if use_vault and self.VAULT_FILE.exists():
            self._load_from_vault(vault_password)
            
        # 3. Load from HashiCorp Vault if enabled
        if use_hashicorp:
            self._load_from_hashicorp()
        
        # 4. Inject all found credentials into environment variables
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

    def _load_from_hashicorp(self):
        """Fetches credentials from HashiCorp Vault (KVv2)."""
        addr = os.environ.get("VAULT_ADDR")
        token = os.environ.get("VAULT_TOKEN")
        mount = os.environ.get("VAULT_MOUNT", self.DEFAULT_HC_MOUNT)
        path = os.environ.get("VAULT_PATH", self.DEFAULT_HC_PATH)
        
        if not addr or not token:
            logger.warning("HashiCorp Vault enabled but VAULT_ADDR or VAULT_TOKEN not found in environment.")
            return

        logger.info(f"Connecting to HashiCorp Vault at {addr}...")
        try:
            import hvac
            client = hvac.Client(url=addr, token=token)
            if not client.is_authenticated():
                logger.error("HashiCorp Vault authentication failed.")
                return
                
            read_response = client.secrets.kv.v2.read_secret_version(path=path, mount_point=mount)
            hc_creds = read_response['data']['data']
            
            # Ensure we are dealing with strings as expected by the rest of the app
            self._credentials.update({k: str(v) for k, v in hc_creds.items()})
            logger.info(f"Successfully loaded {len(hc_creds)} credentials from HashiCorp Vault ({mount}/{path})")
            
        except ImportError:
            logger.error("hvac library not found. Please install it with 'pip install hvac'.")
        except Exception as e:
            logger.error(f"Failed to fetch from HashiCorp Vault: {e}")

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

    @classmethod
    def seal_to_hashicorp(cls, credentials: Dict[str, str]):
        """Uploads credentials to HashiCorp Vault (KVv2)."""
        addr = os.environ.get("VAULT_ADDR")
        token = os.environ.get("VAULT_TOKEN")
        mount = os.environ.get("VAULT_MOUNT", cls.DEFAULT_HC_MOUNT)
        path = os.environ.get("VAULT_PATH", cls.DEFAULT_HC_PATH)
        
        if not addr or not token:
            logger.error("VAULT_ADDR and VAULT_TOKEN must be set to use HashiCorp Vault.")
            return False

        try:
            import hvac
            client = hvac.Client(url=addr, token=token)
            client.secrets.kv.v2.create_or_update_secret(path=path, secret=credentials, mount_point=mount)
            logger.info(f"Successfully uploaded credentials to HashiCorp Vault at {mount}/{path}")
            return True
        except ImportError:
            logger.error("hvac library not found. Please install it with 'pip install hvac'.")
        except Exception as e:
            logger.error(f"Failed to upload to HashiCorp Vault: {e}")
        return False

# Singleton instance for easy access
_instance: Optional[CredentialsHelper] = None

def get_helper(password: Optional[str] = None, use_vault: bool = True, use_hashicorp: bool = False) -> CredentialsHelper:
    global _instance
    if _instance is None:
        _instance = CredentialsHelper(password, use_vault, use_hashicorp)
    else:
        # If the singleton was already created without HashiCorp, but it's now requested, we must load it.
        # Check if we should re-load HashiCorp
        was_hashicorp_loaded = getattr(_instance, '_hashicorp_loaded', False)
        if use_hashicorp and not was_hashicorp_loaded:
            _instance._load_from_hashicorp()
            _instance._hashicorp_loaded = True
            _instance._inject_into_env()
    return _instance

def get_credential(key: str, default: Optional[str] = None) -> Optional[str]:
    return get_helper().get_credential(key, default)
