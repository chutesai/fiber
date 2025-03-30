"""
THIS IS AN EXAMPLE FILE OF A SUBNET ENDPOINT!

PLEASE IMPLEMENT YOUR OWN :)
"""

from functools import partial

from fastapi import Depends
from fastapi.routing import APIRouter
from pydantic import BaseModel

from fiber.encrypted.miner.dependencies import blacklist_low_stake, verify_get_request, verify_request
from fiber.encrypted.miner.security.encryption import decrypt_general_payload


class ExampleSubnetRequest(BaseModel):
    pass


async def example_subnet_request(
    decrypted_payload: ExampleSubnetRequest = Depends(
        partial(decrypt_general_payload, ExampleSubnetRequest),
    ),
):
    return {"status": "Example request received"}


async def example_subnet_get():
    return {"status": "Example get request received"}


def factory_router() -> APIRouter:
    router = APIRouter()
    router.add_api_route(
        "/example-subnet-request",
        example_subnet_request,
        tags=["Example"],
        dependencies=[Depends(blacklist_low_stake), Depends(verify_request)],
        methods=["POST"],
    )
    router.add_api_route(
        "/example-subnet-get",
        example_subnet_get,
        tags=["Example"],
        dependencies=[Depends(blacklist_low_stake), Depends(verify_get_request)],
        methods=["GET"],
    )
    return router
