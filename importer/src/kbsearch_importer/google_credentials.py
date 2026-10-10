from __future__ import annotations

import json
from kbsearch_importer import config
from kbsearch_importer.config import ConfigError


def ensure_google_application_credentials() -> str:
    """Validate the service account JSON supplied through the config mount."""
    adc_path = config.DEFAULT_GCP_ADC_FILE
    if not adc_path.is_file():
        raise ConfigError(f"Google ADC file not found: {adc_path}")

    return str(adc_path)


def load_service_account_email() -> str:
    """Read service account email from the configured ADC JSON file."""
    adc_path = ensure_google_application_credentials()

    try:
        with open(adc_path, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Unable to read Google ADC file: {adc_path}") from exc

    if not isinstance(payload, dict):
        raise ConfigError(f"Google ADC file must contain a JSON object: {adc_path}")

    client_email = payload.get("client_email")
    if not isinstance(client_email, str) or client_email.strip() == "":
        raise ConfigError(f"Google ADC file is missing client_email: {adc_path}")

    return client_email.strip()
