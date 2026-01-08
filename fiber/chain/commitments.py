from typing import Any

from scalecodec import ScaleType
from substrateinterface import Keypair, SubstrateInterface
from tenacity import retry, stop_after_attempt, wait_exponential

from fiber.chain.chain_utils import format_error_message
from fiber.chain.models import CommitmentDataField, CommitmentDataFieldType, CommitmentQuery, RawCommitmentQuery
from fiber.constants import EMPTY_COMMITMENT_FIELD_TYPE
from fiber.logging_utils import get_logger

logger = get_logger(__name__)


def _serialize_commitment_field(field: CommitmentDataField) -> dict[str, bytes]:
    if not field:
        return {EMPTY_COMMITMENT_FIELD_TYPE: b''}

    data_type, data = field

    if data_type == CommitmentDataFieldType.RAW:
        serialized_data_type = CommitmentDataFieldType.RAW.value + str(len(data))
    else:
        serialized_data_type = data_type.value

    return {serialized_data_type: data}


def _deserialize_commitment_field(field: dict[str, Any]) -> CommitmentDataField:
    # Extract the single key/value pair
    data_type, data = next(iter(field.items()))

    # Handle explicit empty marker
    if data_type == EMPTY_COMMITMENT_FIELD_TYPE:
        return None

    # Normalize the payload into bytes
    def _normalize_to_bytes(value: Any) -> bytes:
        if isinstance(value, (bytes, bytearray)):
            return bytes(value)
        if isinstance(value, str):
            # Expect hex string like 0x... ; fall back to utf-8 if not hex
            if value.startswith("0x"):
                return bytes.fromhex(value[2:])
            return value.encode("utf-8")
        if isinstance(value, (list, tuple)):
            # Unwrap single-element nesting like ((1,2,3),)
            current: Any = value
            while isinstance(current, (list, tuple)) and len(current) == 1 and isinstance(current[0], (list, tuple)):
                current = current[0]
            # Sequence of integers
            return bytes(current)
        # Last resort: string conversion
        return str(value).encode("utf-8")

    # Support Raw fields that may include a length suffix (e.g., "Raw83")
    if data_type.startswith(CommitmentDataFieldType.RAW.value):
        suffix = data_type[len(CommitmentDataFieldType.RAW.value):]
        expected_length = int(suffix) if suffix.isdigit() else None
        data_type = CommitmentDataFieldType.RAW.value
        data_bytes = _normalize_to_bytes(data)
        if expected_length is not None and len(data_bytes) != expected_length:
            raise ValueError(
                f"Got commitment raw field expecting {expected_length} data but got {len(data_bytes)} data"
            )
        return (CommitmentDataFieldType(data_type), data_bytes)

    # Non-raw fields
    data_bytes = _normalize_to_bytes(data)
    return (CommitmentDataFieldType(data_type), data_bytes)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
def _query_commitment(
    substrate: SubstrateInterface,
    netuid: int,
    hotkey: str,
    block: int | None = None,
) -> ScaleType:
    return substrate.query(
        module="Commitments",
        storage_function="CommitmentOf",
        params=[netuid, hotkey],
        block_hash=(None if block is None else substrate.get_block_hash(block)),  # type: ignore
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1.5, min=2, max=5),
    reraise=True,
)
def set_commitment(
    substrate: SubstrateInterface,
    keypair: Keypair,
    netuid: int,
    fields: list[CommitmentDataField],
    wait_for_inclusion: bool = False,
    wait_for_finalization: bool = False,
) -> bool:
    """
    Commit custom fields to the chain
    Arguments:
        fields: A list of fields as data type to value tuples, for example (CommitmentDataFieldType.RAW, b'hello world')
    """

    mapped_fields = [[
        _serialize_commitment_field(field)
        for field in fields
    ]]

    substrate.close()

    call = substrate.compose_call(
        call_module="Commitments",
        call_function="set_commitment",
        call_params={
            "netuid": netuid,
            "info": {
                "fields": mapped_fields,
            },
        },
    )

    extrinsic_to_send = substrate.create_signed_extrinsic(call=call, keypair=keypair)

    response = substrate.submit_extrinsic(
        extrinsic_to_send,
        wait_for_inclusion=wait_for_inclusion,
        wait_for_finalization=wait_for_finalization,
    )

    if not wait_for_finalization and not wait_for_inclusion:
        logger.info("Not waiting for finalization or inclusion.")
        return True

    response.process_events()

    substrate.close()

    if response.is_success:
        if wait_for_finalization:
            logger.info("✅ Successfully committed and finalized")
        elif wait_for_inclusion:
            logger.info("✅ Successfully committed and included")
        else:
            logger.info("✅ Successfully committed")

        return True
    else:
        logger.error(f"❌ Failed to commit: {format_error_message(response.error_message)}")

        return False


def query_commitment(
    substrate: SubstrateInterface,
    netuid: int,
    hotkey: str,
    block: int | None = None,
) -> CommitmentQuery | None:
    """
    Query fields committed to the chain via set_commitment
    return: None if no commitment has been made previously, otherwise CommitmentQuery
    """

    value = _query_commitment(
        substrate,
        netuid,
        hotkey,
        block,
    )

    if not value:
        return None

    # The chain may return nested tuples/lists, e.g., (({...},),)
    raw_fields: Any = value["info"]["fields"]

    # Unwrap nested containers until we get a sequence of dicts
    def _unwrap_fields(container: Any) -> list[dict[str, Any]]:
        current = container
        while True:
            if current is None:
                return []
            if isinstance(current, dict):
                # Single dict; wrap in list
                return [current]
            if isinstance(current, (list, tuple)):
                if len(current) == 0:
                    return []
                first = current[0]
                if isinstance(first, dict):
                    return list(current)  # type: ignore[return-value]
                # Keep unwrapping one level
                current = first
                continue
            # Unknown shape; return empty to be safe
            return []

    fields_list = _unwrap_fields(raw_fields)
    mapped_fields = [_deserialize_commitment_field(field) for field in fields_list]

    return CommitmentQuery(
        fields=mapped_fields,
        block=value["block"],
        deposit=value["deposit"],
    )


def publish_raw_commitment(
    substrate_interface: SubstrateInterface,
    keypair: Keypair,
    netuid: int,
    data: bytes,
    wait_for_inclusion: bool = False,
    wait_for_finalization: bool = True,
):
    """
    Helper function for publishing a single raw byte-string to the chain using only one commitment field
    """

    return set_commitment(
        substrate_interface,
        keypair,
        netuid,
        [(CommitmentDataFieldType.RAW, data)],
        wait_for_inclusion,
        wait_for_finalization
    )


def get_raw_commitment(
    substrate: SubstrateInterface,
    netuid: int,
    hotkey: str,
    block: int | None = None,
) -> RawCommitmentQuery | None:
    """
    Helper function for getting single field raw byte-string value after publishing with publish_raw_commitment
    returns: None if publish_raw_commitment has not been called before
    raises: ValueError if set_commitment has been called before with a different data-type
    """

    commitment = query_commitment(substrate, netuid, hotkey, block)
    if commitment and len(commitment.fields):
        field = commitment.fields[0]
    else:
        field = None

    if not field:
        return None

    data_type, data = field

    if data_type != CommitmentDataFieldType.RAW:
        raise ValueError(
            f"Commitment for {hotkey} in netuid {netuid} is of type {data_type.value} and not {CommitmentDataFieldType.RAW.value}"
        )

    if commitment is None:
        return None

    return RawCommitmentQuery(
        data=data,
        block=commitment.block,
        deposit=commitment.deposit,
    )
