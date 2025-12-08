"""Configuration management for hwman using Pydantic Settings."""

import logging
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

logger = logging.getLogger(__name__)


class HwmanSettings(BaseSettings):
    """Main configuration for hwman loaded from TOML file."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    # Server settings
    server_address: str = Field(default="localhost", description="Server address to bind to")
    server_port: int = Field(default=50001, description="Server port to bind to")
    log_level: str = Field(
        default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )

    # Certificate settings
    cert_dir: Path = Field(
        default=Path("./certs"), description="Directory for certificates"
    )

    # InstrumentServer settings
    instrumentserver_config_file: Path = Field(
        default=Path("./configs/serverConfig.yml"),
        description="Path to instrumentserver config file",
    )
    instrumentserver_params_file: Path = Field(
        default=Path("./configs/parameter_manager-parameter_manager.json"),
        description="Path to parameter manager JSON file",
    )

    # Pyro nameserver settings
    pyro_proxy_name: str = Field(
        default="rfsoc", description="Name of the Pyro nameserver proxy"
    )
    pyro_ns_host: str = Field(default="localhost", description="Pyro nameserver host")
    pyro_ns_port: int = Field(default=8888, description="Pyro nameserver port")

    # QICK server settings (SSH connection)
    qick_ssh_host: str = Field(
        default="", description="SSH alias or hostname for the QICK board (e.g., 'qick_board', leave empty to disable)"
    )
    qick_ssh_password: str = Field(
        default="", description="SSH/sudo password for QICK board (leave empty if not needed)"
    )
    qick_remote_path: str = Field(
        default="/home/xilinx/jupyter_notebooks/qick/pyro4",
        description="Path to QICK pyro4 directory on remote board",
    )
    qick_board: str = Field(
        default="ZCU216", description="BOARD environment variable for QICK"
    )
    qick_virtual_env: str = Field(
        default="/usr/local/share/pynq-venv",
        description="Virtual environment path on remote board",
    )
    qick_xilinx_xrt: str = Field(
        default="/usr", description="XILINX_XRT path on remote board"
    )

    # Data settings
    data_dir: Path = Field(
        default=Path("./data"), description="Directory for experimental data"
    )
    fake_calibration_data: bool = Field(
        default=False,
        description="Use fake calibration data for testing without hardware",
    )

    # Service startup
    start_external_services: bool = Field(
        default=True, description="Start external services on server startup"
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a valid Python logging level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(
                f"Invalid log level '{v}'. Must be one of: {', '.join(valid_levels)}"
            )
        return v.upper()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type["BaseSettings"],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources to load from TOML file.

        This method implements the Pydantic settings sources API to support loading
        configuration from a TOML file. It prioritizes init_settings (which can pass
        a custom toml file path via _toml_file) over the TOML file source.
        """
        # Get the TOML file path from init_settings if provided (_toml_file),
        # otherwise use default
        init_data = init_settings() if callable(init_settings) else {}
        toml_path = init_data.get("_toml_file") or Path("config.toml")

        # Only create TomlConfigSettingsSource if the file exists
        toml_source = None
        if Path(toml_path).exists():
            toml_source = TomlConfigSettingsSource(settings_cls, str(toml_path))

        # Build sources in priority order (higher priority = checked first)
        sources: list[PydanticBaseSettingsSource] = [
            init_settings,  # Highest priority - constructor arguments
        ]

        if toml_source:
            sources.append(toml_source)

        sources.extend([
            env_settings,  # Environment variables
            dotenv_settings,  # .env file
            file_secret_settings,  # File-based secrets
        ])

        return tuple(sources)

    def to_dict(self) -> dict:
        """Convert configuration to dictionary (useful for logging).

        Returns:
            Dictionary representation
        """
        return self.model_dump(mode="python")