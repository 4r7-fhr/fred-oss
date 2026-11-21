"""Which parts of a request reach an endpoint function's arguments."""
import asyncio

from fred.rest.router.endpoint import RouterEndpointAnnotation, RouterEndpointConfig
from fred.rest.router.interface import RouterInterfaceMixin

HEADERS = {
    "host": "runner.internal",
    "x-api-key": "the-runner-token",
    "authorization": "Bearer something",
    "content-type": "application/json",
}


class FakeRequest:
    """The parts of a Starlette request the endpoint closure reads."""

    def __init__(self, method="POST", headers=None, path_params=None, query_params=None, body=None):
        self.method = method
        self.headers = dict(HEADERS if headers is None else headers)
        self.path_params = dict(path_params or {})
        self.query_params = dict(query_params or {})
        self._body = body

    async def json(self):
        if self._body is None:
            raise ValueError("no JSON body")
        return self._body


class EchoMixin(RouterInterfaceMixin):

    @RouterEndpointAnnotation.set(path="/with", methods=["POST"])
    def with_headers(self, **kwargs) -> dict:
        return kwargs

    @RouterEndpointAnnotation.set(path="/without/{item}", methods=["POST"], include_headers=False)
    def without_headers(self, **kwargs) -> dict:
        return kwargs


def call(name: str, request: FakeRequest) -> dict:
    endpoint = EchoMixin.__dict__[name].__get__(None, EchoMixin)
    return asyncio.run(endpoint.function(request))


def test_by_default_an_endpoint_still_receives_the_headers():
    received = call("with_headers", FakeRequest(body={"prompt": "a cat"}))

    assert received == {**HEADERS, "prompt": "a cat"}


def test_an_endpoint_that_opts_out_receives_no_header():
    request = FakeRequest(path_params={"item": "7"}, query_params={"verbose": "1"}, body={"prompt": "a cat"})

    received = call("without_headers", request)

    assert received == {"item": "7", "verbose": "1", "prompt": "a cat"}
    assert not set(HEADERS) & set(received)


def test_opting_out_does_not_hide_a_body_key_that_is_named_like_a_header():
    received = call("without_headers", FakeRequest(body={"host": "from-the-body", "prompt": "a cat"}))

    assert received == {"host": "from-the-body", "prompt": "a cat"}


def test_the_option_is_kept_out_of_the_route_registration():
    default = RouterEndpointConfig.auto(path="/a", methods=["GET"], tags=["x"])
    opted_out = RouterEndpointConfig.auto(path="/b", methods=["POST"], tags=["x"], include_headers=False)

    assert default.include_headers is True and opted_out.include_headers is False
    # FastAPI's add_api_route receives `configs`; it does not know include_headers.
    assert default.configs == {"tags": ["x"]} and opted_out.configs == {"tags": ["x"]}
    endpoint = EchoMixin.__dict__["without_headers"].__get__(None, EchoMixin)
    assert endpoint.route_config() == {"path": "/without/{item}", "methods": ["POST"]}
