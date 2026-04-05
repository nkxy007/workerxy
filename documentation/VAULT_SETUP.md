# 🔐 Secure Credential Vault Management

WorkerXY supports two ways to secure your sensitive API keys (OpenAI, Anthropic, ServiceNow, etc.): a **Local Encrypted Vault** and a **HashiCorp Vault Integration**.

---

## 🛡️ Local Encrypted Vault

The local vault encrypts your `creds.json` into a single file (`~/.creds.vault`) using AES-256 (Fernet) with a key derived from your password.

### 1. Sealing Credentials
If you have an existing `creds.json` file, you can seal it into the vault:
```bash
workerxy vault seal
```
- You will be prompted to set a strong password.
- **IMPORTANT**: The system does not store this password. If you lose it, your credentials cannot be recovered.
- After sealing, the tool will offer to delete the plain-text `creds.json` for security.

### 2. Viewing Contents
To see what's currently inside your vault:
```bash
workerxy vault view
```

### 3. Usage by the Agent
The agent automatically detects the presence of `~/.creds.vault`. At startup, it will prompt you for your decryption password.

---

## ☁️ HashiCorp Vault Integration (KVv2)

For teams or distributed deployments, you can store and retrieve credentials using a centralized HashiCorp Vault instance.

### ⚙️ Prerequisites
1.  **Library**: Install the HashiCorp Vault client:
    ```bash
    pip install hvac
    ```
2.  **Environment Variables**:
    Export the following variables in your shell:
    ```bash
    export VAULT_ADDR='http://your-vault-url:8200'
    export VAULT_TOKEN='your-access-token'
    
    # Optional (defaults shown)
    export VAULT_MOUNT='secret'
    export VAULT_PATH='workerxy'
    ```

### 1. Uploading to HashiCorp
If you have a local `creds.json` and want to move it to the cloud:
```bash
workerxy vault seal --hashicorp
```

### 2. Running the Agent with HashiCorp
To force the agent to fetch credentials from HashiCorp instead of local files, use the `--hashicorp` flag:
```bash
workerxy cli --hashicorp
# or
workerxy start-all --hashicorp
```

### 3. Viewing Remote Contents
```bash
workerxy vault view --hashicorp
```

---

## 🛡️ Best Practices
- **Delete Plain-Text Files**: Once you've sealed your credentials into either vault, always delete the `creds.json` and `creds.py` files.
- **Use unique tokens**: For HashiCorp, use a token with restricted access to the `workerxy` path only.
- **Password Managers**: Store your local vault password in a trusted password manager.
