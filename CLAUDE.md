# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`lccfq-hwman` is a hardware manager for the Pfafflab Quantum Processing Unit (QPU). It provides a gRPC-based server with mutual TLS authentication that manages quantum hardware components including the QICK (Quantum Instrumentation Control Kit) board, instrument servers, and experimental setups. The system orchestrates external services like instrumentserver (via QCoDeS), Pyro nameserver for remote object communication, and QICK server for quantum operations.

## Architecture

### Core Components

- **gRPC Server** (`hwman/main.py`): The central `Server` class manages the gRPC server lifecycle, certificate initialization, and service coordination. Uses ThreadPoolExecutor with 10 workers and enforces mutual TLS.

- **Services** (`hwman/services/`): Each service inherits from the abstract `Service` base class which requires a `cleanup()` method:
  - `HealthService`: Manages external processes (instrumentserver, Pyro nameserver, QICK server), provides health checks, and handles process lifecycle
  - `TestService`: Executes quantum experiments, manages calibration data, and stores results in the data directory

- **CLI** (`hwman/cli.py`): Uses Typer for command-line interface. The `start` command launches the server by loading configuration from a TOML file. Features custom colored logging with service-specific colors.

- **Configuration** (`hwman/config.py`): Uses Pydantic BaseSettings to load all server configuration from a TOML file. Includes validation and type conversion for all settings.

- **Certificate Management** (`hwman/certificates/`): `CertificateManager` handles creation and management of CA certificates, server certificates, and client certificates for mutual TLS authentication.

- **gRPC Protocol**:
  - `.proto` files in `hwman/grpc/protobufs/` define the service contracts
  - Compiled stubs in `hwman/grpc/protobufs_compiled/` are auto-generated (never edit manually)
  - Services include health checking, experiment execution, and user management

- **Client** (`hwman/client/client.py`): Python client implementation for connecting to the gRPC server with mTLS

- **Hardware Tests** (`hwman/hw_tests/`): Quantum calibration and characterization experiments including resonator spectroscopy, Rabi oscillations, T1/T2 measurements, and full calibration sequences

- **Utilities** (`hwman/utils/`): Shared fitting and plotting functions for experiment data analysis

### External Service Management

The `HealthService` manages three critical external processes:
1. **instrumentserver**: QCoDeS-based instrument control server
2. **Pyro nameserver**: Remote object nameserver for RFSoC communication
3. **QICK server**: Runs on the QICK board via SSH with credentials and connection parameters from the config file

### Data Organization

- **Configuration**: `configs/` contains `serverConfig.yml` for instrumentserver and parameter manager JSON files
- **Data Storage**: `data/` directory stores experimental results, organized by date
- **Certificates**: `certs/` stores CA, server, and client certificates (auto-generated if missing)

## Commands

### Build/Compilation

```bash
# Compile protobuf files (required before running)
make

# Or explicitly
make protos

# Clean compiled protobufs
make clean
```

The Makefile compiles `.proto` files from `hwman/grpc/protobufs/` into Python stubs, flattens the output directory structure, and fixes import paths.

### Running the Server

All configuration is now done through a TOML file. Create a `config.toml` file in your project root by copying from the example:

```bash
# Copy the example configuration
cp configs/example_config.toml config.toml

# Edit the config file with your settings
nano config.toml

# Start the server with the config file
uv run hwman start -c config.toml

# Or use the default config file location (config.toml)
uv run hwman start
```

The configuration file is a TOML file that includes all settings for the server, including the gRPC server settings, instrumentserver configuration, Pyro nameserver settings, and QICK SSH configuration.

### Configuration File Format

The `config.toml` file uses the following structure:

```toml
# Server settings
server_address = "localhost"      # Server bind address
server_port = 50001              # Server port
log_level = "INFO"               # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Certificate directory
cert_dir = "./certs"

# InstrumentServer configuration
instrumentserver_config_file = "./configs/serverConfig.yml"
instrumentserver_params_file = "./configs/parameter_manager-parameter_manager.json"

# Pyro nameserver (for QICK communication)
pyro_proxy_name = "rfsoc"        # Must match QICK configuration
pyro_ns_host = "localhost"
pyro_ns_port = 8888

# QICK server SSH configuration (REQUIRED for hardware)
qick_ssh_host = "qick_board"             # SSH alias or hostname (uses sudo -S for password auth)
qick_ssh_password = "xilinx"             # Password for sudo commands on QICK board
qick_remote_path = "/home/xilinx/jupyter_notebooks/qick/pyro4"
qick_board = "ZCU216"
qick_virtual_env = "/usr/local/share/pynq-venv"
qick_xilinx_xrt = "/usr"

# Data and operation settings
data_dir = "./data"              # Directory for experimental data
fake_calibration_data = false    # true for testing without hardware

# Service startup
start_external_services = true   # Start instrumentserver, Pyro nameserver, and QICK server
```

**QICK SSH Configuration**: The QICK SSH settings unify all QICK connection parameters in the configuration file. All SSH credentials and paths are now managed through the TOML config instead of environment variables.

### Development

```bash
# Install dependencies
uv sync

# Install with dev dependencies
uv sync --group dev

# Type checking (mypy configuration in pyproject.toml)
uv run mypy hwman/

# Linting/formatting (ruff configuration in pyproject.toml)
uv run ruff check hwman/
uv run ruff format hwman/

# Run JupyterLab (for analysis notebooks)
uv run jupyter lab
```

## Development Guidelines

### Code Style

- **Type Hints**: Required for all function definitions (enforced by mypy with `disallow_untyped_defs`)
- **Paths**: Always use `pathlib.Path`, never string concatenation
- **Imports**: Generated protobuf files are ignored by mypy and ruff (see tool configurations in `pyproject.toml`)
- **Logging**: Use structured logging with logger names (e.g., `logger = logging.getLogger(__name__)`)

### Working with gRPC

1. Edit `.proto` files in `hwman/grpc/protobufs/`
2. Run `make` to regenerate Python stubs
3. Import from `hwman.grpc.protobufs_compiled` (not from protobufs directly)
4. Implement service methods by inheriting from generated servicer classes

### Security Context

- **mTLS Required**: All client-server communication uses mutual TLS
- **SSH Setup**: The QICK board is accessed via SSH using an alias configured in `~/.ssh/config` (e.g., `qick_board`). The `sudo` commands on the remote board use password-based authentication via the `-S` flag, with the password stored in `config.toml`
- **Network Architecture**: Server runs on a machine with dual network access (external network + private intranet for QICK board)
- **Certificate Manager**: Handles automatic certificate generation; certificates stored in `certs/`

### Local Dependencies

The project depends on several local editable packages (see `[tool.uv.sources]` in `pyproject.toml`):
- `labcore`: Core laboratory utilities (from `../labcore`)
- `instrumentserver`: Instrument control server (from `../instrumentserver`)
- `qcui_measurement`: Measurement utilities (from `../measurement`)
- `qcui_analysis`: Analysis utilities (from `../analysis`)
- `qick`: QICK board interface (from `../qick`)

These must be available as sibling directories to this repository.

### Environment Variables

The CLI loads environment variables from `.env` in the project root if present. Use this for configuration that shouldn't be in version control.

### Configuration Management

All server configuration is managed through Pydantic BaseSettings (`hwman/config.py`). Configuration is loaded from a TOML file using the `HwmanSettings` class:

- Configuration is loaded from `config.toml` by default (or specified with `-c` flag)
- All settings are validated by Pydantic (type checking, range validation, etc.)
- Path fields are automatically converted from strings to `pathlib.Path` objects
- The server receives a single `HwmanSettings` object, which is cleaner than individual parameters

## Important Notes

- **Never edit** files in `hwman/grpc/protobufs_compiled/` - they are auto-generated
- **Always run** `make` after modifying `.proto` files
- **Configuration file required**: The server needs a valid `config.toml` file to start
- **SSH alias setup**: Configure the QICK board access in `~/.ssh/config` for your SSH alias before deploying
- Python version is pinned to 3.12.* (see `pyproject.toml`)
