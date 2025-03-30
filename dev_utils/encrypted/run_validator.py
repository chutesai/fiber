import os

from dotenv import load_dotenv

load_dotenv("dev.env")
import asyncio

import httpx
from cryptography.fernet import Fernet

from fiber.chain import chain_utils
from fiber.encrypted.validator import client as vali_client
from fiber.encrypted.validator import handshake
from fiber.logging_utils import get_logger

logger = get_logger(__name__)


async def main():
    # Load needed stuff
    wallet_name = os.getenv("WALLET_NAME", "default")
    hotkey_name = os.getenv("HOTKEY_NAME", "default")
    keypair = chain_utils.load_hotkey_keypair(wallet_name, hotkey_name)
    httpx_client = httpx.AsyncClient()

    # Handshake with miner
    miner_address = "http://localhost:7999"
    miner_hotkey_ss58_address = "5xyz_some_miner_hotkey"
    symmetric_key_str, symmetric_key_uuid = await handshake.perform_handshake(
        keypair=keypair,
        httpx_client=httpx_client,
        server_address=miner_address,
        miner_hotkey_ss58_address=miner_hotkey_ss58_address,
    )

    if symmetric_key_str is None or symmetric_key_uuid is None:
        raise ValueError("Symmetric key or UUID is None :-(")
    else:
        logger.info("Wohoo - handshake worked! :)")

    fernet = Fernet(symmetric_key_str)

    resp = await vali_client.make_non_streamed_post(
        httpx_client=httpx_client,
        server_address=miner_address,
        fernet=fernet,
        keypair=keypair,
        symmetric_key_uuid=symmetric_key_uuid,
        validator_ss58_address=keypair.ss58_address,
        miner_ss58_address=miner_hotkey_ss58_address,
        payload={},
        endpoint="/example-subnet-request",
    )
    resp.raise_for_status()
    logger.info(f"Example request sent! Response: {resp.text}")

    resp = await vali_client.make_non_streamed_get(
        httpx_client=httpx_client,
        server_address=miner_address,
        validator_ss58_address=keypair.ss58_address,
        symmetric_key_uuid=symmetric_key_uuid,
        miner_ss58_address=miner_hotkey_ss58_address,
        keypair=keypair,
        endpoint="/example-subnet-get",
    )
    resp.raise_for_status()
    logger.info(f"Example get request sent! Response: {resp.text}")


if __name__ == "__main__":
    asyncio.run(main())
