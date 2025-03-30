import base64

from cryptography.fernet import Fernet

from fiber.logging_utils import get_logger

logger = get_logger(__name__)


def fernet_to_symmetric_key(fernet: Fernet) -> str:
    return base64.urlsafe_b64encode(fernet._signing_key + fernet._encryption_key).decode()


def construct_header_signing_message(nonce: str, miner_hotkey: str, validator_hotkey: str, payload_hash: str | None) -> str:
    if payload_hash is None:
        return f"{nonce}:{miner_hotkey}:{validator_hotkey}"
    return f"{nonce}:{miner_hotkey}:{validator_hotkey}:{payload_hash}"
