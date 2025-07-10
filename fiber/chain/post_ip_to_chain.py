import netaddr
import socket
from substrateinterface import Keypair, SubstrateInterface
from tenacity import retry, stop_after_attempt, wait_exponential

from fiber.logging_utils import get_logger

logger = get_logger(__name__)


def resolve_hostname_to_ip(hostname: str) -> str:
    """
    Resolve a hostname to an IP address.
    
    Args:
        hostname: The hostname to resolve (e.g., 'example.com')
        
    Returns:
        The resolved IP address as a string
        
    Raises:
        socket.gaierror: If the hostname cannot be resolved
    """
    try:
        # First check if it's already an IP address
        netaddr.IPAddress(hostname)
        logger.info(f"'{hostname}' is already an IP address")
        return hostname
    except netaddr.AddrFormatError:
        # It's not an IP address, try to resolve as hostname
        logger.info(f"Resolving hostname '{hostname}' to IP address")
        ip_address = socket.gethostbyname(hostname)
        logger.info(f"Resolved '{hostname}' to '{ip_address}'")
        return ip_address


def ip_to_int(str_val: str) -> int:
    return int(netaddr.IPAddress(str_val))


def ip_version(str_val: str) -> int:
    """Returns the ip version (IPV4 or IPV6)."""
    return int(netaddr.IPAddress(str_val).version)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
def post_node_ip_to_chain(
    substrate: SubstrateInterface,
    keypair: Keypair,
    netuid: int,
    external_ip: str,
    external_port: int,
    coldkey_ss58_address: str,
    wait_for_inclusion=False,
    wait_for_finalization=True,
) -> bool:
    # Resolve hostname to IP if needed
    resolved_ip = resolve_hostname_to_ip(external_ip)
    
    params = {
        "version": 1,  # I don't know why we even post this, can we just post 1?
        "ip": ip_to_int(resolved_ip),
        "port": external_port,
        "ip_type": ip_version(resolved_ip),
        "netuid": netuid,
        "hotkey": keypair.ss58_address,
        "coldkey": coldkey_ss58_address,
        "protocol": 4,
        "placeholder1": 0,
        "placeholder2": 0,
    }

    logger.info(f"Posting IP to chain. Params: {params}")

    with substrate as si:
        call = si.compose_call("SubtensorModule", "serve_axon", params)
        extrinsic = si.create_signed_extrinsic(call=call, keypair=keypair)
        response = si.submit_extrinsic(extrinsic, wait_for_inclusion, wait_for_finalization)

        if wait_for_inclusion or wait_for_finalization:
            response.process_events()
            if not response.is_success:
                logger.error(f"Failed: {response.error_message}")
            return response.is_success
    return True
