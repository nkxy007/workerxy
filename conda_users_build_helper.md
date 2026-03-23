# Conda Environment Setup

This package requires a C compiler to build its Rust extensions. Follow the steps below to set up your conda environment correctly.

## Quick Start

The easiest way to get everything set up is via the provided `environment.yml`:

```bash
name: workerxy_env
channels:
  - conda-forge
  - defaults
dependencies:
  - gcc
  - gxx
  - pip
  - pip:
    - -e .
```

```bash
conda env create -f environment.yml
conda activate workerxy_env
```

This installs all required dependencies, including the C compiler, automatically.

## Manual Setup

If you prefer to set up manually or add the package to an existing environment:

```bash
# 1. Install the C compiler
conda install -c conda-forge gcc gxx

# 2. Install the package
pip install -e .
```

## Why is this needed?

This package includes Rust extensions. Even though Rust has its own compiler, it relies on the system C linker (`cc`) to produce the final binary. Without it, installation fails with:

```
error: linker `cc` not found
```

Installing `gcc` and `gxx` via conda-forge provides that linker inside your conda environment, without requiring any system-level changes.

## Troubleshooting

**Still seeing the linker error after installing gcc?**

Make sure you activated your environment before running `pip install`:

```bash
conda activate workerxy_env
which cc  # should point inside your conda env
```

**On Linux without conda?**

```bash
# CentOS/RHEL
sudo dnf groupinstall "Development Tools"

# Ubuntu/Debian
sudo apt install build-essential
```