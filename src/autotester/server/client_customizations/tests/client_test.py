from autotester.server.client_customizations import _CLIENTS
from autotester.server.client_customizations.client import Client


class TestClient:
    pass


for client_class in _CLIENTS.values():

    def func(self):
        """ Checks if all abstract methods in Client are implemented """
        assert not Client.__abstractmethods__ - set(vars(client_class).keys())

    setattr(TestClient, f"test_{client_class}_implements_all_abstract", func)
