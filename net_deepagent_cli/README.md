# Net DeepAgent CLI

A powerful terminal interface for interacting with the Net DeepAgent.

## Features

- **Rich Terminal UI**: Beautiful markdown rendering and progress indicators.
- **Human-in-the-loop**: Approval workflow for sensitive network operations.
- **Middleware System**: Memory and skills injection.
- **Automata**: Scheduled background tasks now powered by the `automata_agent` subagent for programmatic control (see [AUTOMATA.md](AUTOMATA.md)).
- **Slash Commands**: `/help`, `/clear`, `/tokens`, `/skills`, `/memory`, `/exit`, `/automata`.

## Usage

Run the CLI using:

```bash
python -m net_deepagent_cli
```

Or install it as a package and use:

```bash
net-deepagent
```

## Configuration

Configuration is stored in `~/.net-deepagent/<agent-name>/config.yaml`.
History and memories are also stored in the same directory.

## Credential Management

The system uses a centralized `CredentialsHelper` to load API keys and SSH credentials. Keys are sourced in the following order of priority:
1. Environment variables (e.g., `OPENAI_API_KEY`)
2. Encrypted Vault (`~/.creds.vault`)
3. Centralized JSON config (`~/.net-deepagent/creds.json`)
4. Legacy `creds.py` (Deprecated Fallback)

### Encrypted Vault
You can store your credentials securely in an encrypted vault. If a vault is detected, the CLI will prompt you for the decryption password at startup.

To create a new vault:
```python
from utils.credentials_helper import CredentialsHelper
CredentialsHelper.create_vault({"OPENAI_KEY": "sk-...", "ANTHROPIC_KEY": "sk-ant-..."}, "your-password")
```
