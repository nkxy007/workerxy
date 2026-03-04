import os
import sys
import json
import unittest
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.credentials_helper import CredentialsHelper, get_helper, get_credential

class TestVaultFunctionality(unittest.TestCase):
    
    def setUp(self):
        self.vault_file = Path.home() / ".creds.vault"
        self.backup_vault = None
        if self.vault_file.exists():
            self.backup_vault = self.vault_file.with_suffix(".vault.bak")
            self.vault_file.rename(self.backup_vault)
            
        self.test_creds = {
            "VAULT_API_KEY": "vault_secret_123",
            "OPENAI_KEY": "sk-vault-openai-999"
        }
        self.password = "test_password"

    def tearDown(self):
        if self.vault_file.exists():
            self.vault_file.unlink()
        if self.backup_vault and self.backup_vault.exists():
            self.backup_vault.rename(self.vault_file)

    def test_vault_creation_and_loading(self):
        print("\n--- Testing Vault Creation ---")
        CredentialsHelper.create_vault(self.test_creds, self.password)
        self.assertTrue(self.vault_file.exists())
        
        print("\n--- Testing Vault Loading with Password ---")
        # Reset the singleton helper for this test to force reload
        import utils.credentials_helper
        utils.credentials_helper._instance = None
        
        # Test loading with provided password
        helper = CredentialsHelper(vault_password=self.password)
        
        self.assertEqual(helper.get_credential("VAULT_API_KEY"), "vault_secret_123")
        self.assertEqual(helper.get_credential("OPENAI_API_KEY"), "sk-vault-openai-999")
        self.assertEqual(os.environ.get("OPENAI_API_KEY"), "sk-vault-openai-999")
        print("Vault loading successful!")

    @patch("getpass.getpass")
    def test_vault_interactive_prompt(self, mock_getpass):
        print("\n--- Testing Interactive Password Prompt ---")
        CredentialsHelper.create_vault(self.test_creds, self.password)
        mock_getpass.return_value = self.password
        
        import utils.credentials_helper
        utils.credentials_helper._instance = None
        
        # This should trigger getpass
        helper = CredentialsHelper()
        self.assertEqual(helper.get_credential("VAULT_API_KEY"), "vault_secret_123")
        mock_getpass.assert_called()
        print("Interactive prompt successful!")

if __name__ == "__main__":
    unittest.main()
