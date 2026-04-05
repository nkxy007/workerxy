import os
import sys
import json
import getpass
import argparse
from pathlib import Path
from utils.credentials_helper import CredentialsHelper
from net_deepagent_cli.communication.logger import setup_logger

# Initialize logger for vault tool
logger = setup_logger("vault")

def vault_main():
    parser = argparse.ArgumentParser(description="Secure Credential Vault Management")
    subparsers = parser.add_subparsers(dest="subcommand", help="Vault subcommands")

    # Seal subcommand
    seal_parser = subparsers.add_parser("seal", help="Encrypt credentials into a vault file")
    seal_parser.add_argument("--file", type=str, help="Path to JSON credentials file (default: ~/.net-deepagent/creds.json)")
    seal_parser.add_argument("--output", type=str, help="Vault output path (default: ~/.creds.vault)")
    seal_parser.add_argument("--hashicorp", action="store_true", help="Seal credentials to HashiCorp Vault instead of local file")

    # View subcommand
    view_parser = subparsers.add_parser("view", help="Decrypt and view vault contents (requires password)")
    view_parser.add_argument("--vault", type=str, help="Path to vault file (default: ~/.creds.vault)")
    view_parser.add_argument("--hashicorp", action="store_true", help="View credentials from HashiCorp Vault instead of local file")

    args = parser.parse_args(sys.argv[1:])

    if args.subcommand == "seal":
        if getattr(args, "hashicorp", False):
            seal_to_hashicorp(args.file)
        else:
            seal_vault(args.file, args.output)
    elif args.subcommand == "view":
        if getattr(args, "hashicorp", False):
            view_from_hashicorp()
        else:
            view_vault(args.vault)
    else:
        parser.print_help()

def seal_vault(file_path=None, output_path=None):
    if file_path is None:
        file_path = Path.home() / ".net-deepagent" / "creds.json"
    else:
        file_path = Path(file_path)

    if not file_path.exists():
        print(f"Error: Credentials file not found at {file_path}")
        sys.exit(1)

    try:
        with open(file_path, "r") as f:
            credentials = json.load(f)
    except Exception as e:
        print(f"Error reading credentials file: {e}")
        sys.exit(1)

    print(f"\n--- 🔒 Sealing {len(credentials)} credentials into vault ---")
    print("Warning: The system does not store your vault password. If lost, the vault is unrecoverable.")
    
    password = getpass.getpass("Set a strong vault password: ")
    confirm = getpass.getpass("Confirm vault password: ")
    
    if password != confirm:
        print("Error: Passwords do not match.")
        sys.exit(1)

    # Temporary override of the class attribute if a custom output is provided
    original_vault_file = CredentialsHelper.VAULT_FILE
    if output_path:
        CredentialsHelper.VAULT_FILE = Path(output_path)

    try:
        CredentialsHelper.create_vault(credentials, password)
        print(f"Successfully sealed credentials into {CredentialsHelper.VAULT_FILE}")
        
        # After successful sealing, offer to delete the plain-text file
        ans = input(f"\n[?] Remove plain-text credentials file ({file_path}) for better security? [y/N]: ").strip().lower()
        if ans == 'y':
            try:
                os.remove(file_path)
                print(f"[*] Removed {file_path}")
            except Exception as e:
                print(f"Error removing file: {e}")
    finally:
        # Restore the original path
        CredentialsHelper.VAULT_FILE = original_vault_file

def view_vault(vault_path=None):
    if vault_path is None:
        vault_path = Path.home() / ".creds.vault"
    else:
        vault_path = Path(vault_path)

    if not vault_path.exists():
        print(f"Error: Vault file not found at {vault_path}")
        sys.exit(1)

    password = getpass.getpass("Enter vault decryption password: ")
    
    # Use a temporary helper instance to test decryption
    from utils.credentials_helper import CredentialsHelper
    original_vault_file = CredentialsHelper.VAULT_FILE
    CredentialsHelper.VAULT_FILE = vault_path
    
    try:
        # Create an instance which triggers _load_from_vault
        helper = CredentialsHelper(vault_password=password, use_vault=True)
        if helper._credentials:
            print("\n--- 🔓 Vault Contents ---")
            print(json.dumps(helper._credentials, indent=4))
        else:
            print("Vault is empty or decryption failed.")
    except Exception as e:
        print(f"Error: Failed to decrypt vault. {e}")
    finally:
        CredentialsHelper.VAULT_FILE = original_vault_file

def seal_to_hashicorp(file_path=None):
    """Standalone seal logic for HashiCorp Vault."""
    if file_path is None:
        file_path = Path.home() / ".net-deepagent" / "creds.json"
    else:
        file_path = Path(file_path)

    if not file_path.exists():
        print(f"Error: Credentials file not found at {file_path}")
        return

    try:
        with open(file_path, "r") as f:
            credentials = json.load(f)
    except Exception as e:
        logger.error(f"Error reading credentials file: {e}")
        return

    logger.info(f"Sealing {len(credentials)} credentials to HashiCorp Vault...")
    if CredentialsHelper.seal_to_hashicorp(credentials):
        ans = input(f"\n[?] Remove plain-text credentials file ({file_path}) for better security? [y/N]: ").strip().lower()
        if ans == 'y':
            try:
                os.remove(file_path)
                logger.info(f"Removed {file_path}")
            except Exception as e:
                logger.error(f"Error removing file: {e}")

def view_from_hashicorp():
    """Standalone view logic for HashiCorp Vault."""
    logger.info("Fetching from HashiCorp Vault...")
    helper = CredentialsHelper(use_vault=False, use_hashicorp=True)
    if helper._credentials:
        logger.info("HashiCorp Vault Contents retrieved successfully.")
        print("\n--- 📝 HashiCorp Vault Contents ---")
        print(json.dumps(helper._credentials, indent=4))
    else:
        logger.error("No credentials found in HashiCorp Vault or fetch failed.")

if __name__ == "__main__":
    vault_main()
