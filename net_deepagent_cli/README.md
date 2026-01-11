# Net DeepAgent CLI

A powerful terminal interface for interacting with the Net DeepAgent.

## Features

- **Rich Terminal UI**: Beautiful markdown rendering and progress indicators.
- **Human-in-the-loop**: Approval workflow for sensitive network operations.
- **Middleware System**: Memory and skills injection.
- **Slash Commands**: `/help`, `/clear`, `/tokens`, `/skills`, `/memory`, `/exit`.

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
