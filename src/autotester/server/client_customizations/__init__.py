from typing import Dict
from autotester.server.client_customizations import markus, client
ClientType = client.Client

_CLIENTS = {'markus': markus.MarkUs}


def get_client(client_type: str, init_kwargs: Dict) -> ClientType:
    return _CLIENTS[client_type](init_kwargs)
