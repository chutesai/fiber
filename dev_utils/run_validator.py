import os

from dotenv import load_dotenv

load_dotenv("dev.env")
import asyncio

import httpx

from fiber.chain import chain_utils
from fiber.logging_utils import get_logger
from fiber.validator import client as validator

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

    resp = await validator.make_non_streamed_post(
        httpx_client=httpx_client,
        server_address=miner_address,
        keypair=keypair,
        validator_ss58_address=keypair.ss58_address,
        miner_ss58_address=miner_hotkey_ss58_address,
        payload={"hi": "there"},
        endpoint="/example-subnet-request",
    )
    resp.raise_for_status()
    logger.info(f"Example request sent! Response: {resp.text}")

    resp = await validator.make_non_streamed_get(
        httpx_client=httpx_client,
        server_address=miner_address,
        validator_ss58_address=keypair.ss58_address,
        miner_ss58_address=miner_hotkey_ss58_address,
        keypair=keypair,
        endpoint="/example-subnet-get",
    )
    resp.raise_for_status()
    logger.info(f"Example get request sent! Response: {resp.text}")


if __name__ == "__main__":
    asyncio.run(main())
