"""
Configuration Module for Gmail CRM Agent

This module handles environment variable validation and provides
a centralized configuration interface.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv


class Config:
    """Configuration manager for Gmail CRM Agent."""

    def __init__(self, env_path: Optional[Path] = None):
        """
        Initialize configuration from .env file.

        Args:
            env_path: Path to .env file (defaults to project root)
        """
        # Determine project root
        self.project_root = Path(__file__).parent.parent

        # Load .env file
        if env_path is None:
            env_path = self.project_root / ".env"

        if not env_path.exists():
            raise FileNotFoundError(
                f"Error: .env file not found at {env_path}\n"
                "Please create .env file with required configuration."
            )

        load_dotenv(env_path)
        self._validate_required_vars()

    def _validate_required_vars(self) -> None:
        """Validate that all required environment variables are present."""
        # Determine which LLM provider is configured
        model_provider = os.getenv("MODEL_PROVIDER", "openai").lower()

        # Base required variables
        required_vars = [
            "GMAIL_USER",
            "GMAIL_QUERY",
            "GOOGLE_SHEETS_ID",
            "GOOGLE_SHEETS_TAB",
        ]

        # Add provider-specific API key requirement
        if model_provider == "anthropic":
            required_vars.append("ANTHROPIC_API_KEY")
        elif model_provider == "openai":
            required_vars.append("OPENAI_API_KEY")
        else:
            raise ValueError(
                f"Invalid MODEL_PROVIDER: {model_provider}. "
                "Must be 'anthropic' or 'openai'."
            )

        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            raise EnvironmentError(
                f"Error: Missing required environment variables: {', '.join(missing_vars)}\n"
                "Please add them to your .env file."
            )

    # LLM Configuration
    @property
    def model_provider(self) -> str:
        """Get LLM provider (anthropic or openai)."""
        return os.getenv("MODEL_PROVIDER", "openai").lower()

    @property
    def anthropic_api_key(self) -> Optional[str]:
        """Get Anthropic API key."""
        return os.getenv("ANTHROPIC_API_KEY")

    @property
    def openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key."""
        return os.getenv("OPENAI_API_KEY")

    @property
    def anthropic_model(self) -> str:
        """Get Anthropic model name."""
        return os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    @property
    def openai_model(self) -> str:
        """Get OpenAI model name."""
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Gmail Configuration
    @property
    def gmail_user(self) -> str:
        """Get Gmail user email."""
        return os.getenv("GMAIL_USER", "")

    @property
    def gmail_query(self) -> str:
        """Get Gmail search query."""
        return os.getenv("GMAIL_QUERY", "")

    @property
    def gmail_credentials_path(self) -> Path:
        """Get path to Google credentials file."""
        return self.project_root / "credentials.json"

    @property
    def gmail_token_path(self) -> Path:
        """Get path to Google OAuth token file."""
        token_path = os.getenv("GOOGLE_TOKEN_PATH", "token.json")
        return self.project_root / token_path

    # Google Sheets Configuration
    @property
    def sheets_id(self) -> str:
        """Get Google Sheets spreadsheet ID."""
        return os.getenv("GOOGLE_SHEETS_ID", "")

    @property
    def sheets_tab(self) -> str:
        """Get Google Sheets worksheet name."""
        return os.getenv("GOOGLE_SHEETS_TAB", "Leads")

    # Spam Rules Configuration
    @property
    def spam_rules_path(self) -> Path:
        """Get path to spam rules file."""
        spam_rules = os.getenv("SPAM_RULES", "spam_rules.yaml")
        return self.project_root / spam_rules

    # Processing Store Configuration
    @property
    def processed_store_path(self) -> Path:
        """Get path to processed messages store."""
        processed_store = os.getenv("PROCESSED_STORE", "data/processed.jsonl")
        return self.project_root / processed_store

    # Processing Configuration
    @property
    def max_threads(self) -> int:
        """Get maximum number of threads to process."""
        return int(os.getenv("MAX_THREADS", "50"))

    @property
    def poll_interval_seconds(self) -> int:
        """Get polling interval in seconds."""
        return int(os.getenv("POLL_INTERVAL_SECONDS", "300"))

    def to_dict(self) -> Dict[str, Any]:
        """
        Export configuration as dictionary (safe for display).

        Returns:
            Dictionary with configuration values (API keys redacted)
        """
        return {
            "model_provider": self.model_provider,
            "anthropic_model": self.anthropic_model,
            "openai_model": self.openai_model,
            "anthropic_api_key": "***" if self.anthropic_api_key else None,
            "openai_api_key": "***" if self.openai_api_key else None,
            "gmail_user": self.gmail_user,
            "gmail_query": self.gmail_query,
            "sheets_id": self.sheets_id,
            "sheets_tab": self.sheets_tab,
            "spam_rules_path": str(self.spam_rules_path),
            "processed_store_path": str(self.processed_store_path),
            "max_threads": self.max_threads,
            "poll_interval_seconds": self.poll_interval_seconds,
        }

    def print_config(self) -> None:
        """Print configuration in human-readable format."""
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(title="Gmail CRM Agent Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="magenta")

        for key, value in self.to_dict().items():
            table.add_row(key, str(value))

        console.print(table)


def load_config() -> Config:
    """
    Load and validate configuration.

    Returns:
        Config instance

    Raises:
        FileNotFoundError: If .env file not found
        EnvironmentError: If required variables missing
    """
    try:
        return Config()
    except (FileNotFoundError, EnvironmentError) as e:
        print(f"\n{e}\n", file=sys.stderr)
        sys.exit(1)
