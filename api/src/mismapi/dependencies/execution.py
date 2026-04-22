from fastapi import Request

from mismapi.clients.execution_client import ExecutionClient


def get_execution_client(request: Request) -> ExecutionClient:
    client: ExecutionClient = request.app.state.execution_client
    return client
