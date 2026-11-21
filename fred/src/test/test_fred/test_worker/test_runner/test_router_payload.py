"""What the runner's /start and /execute routes pass on: the caller's payload, never its HTTP headers."""
import asyncio
import json
from types import SimpleNamespace

from fred.worker.runner.rest.router._runner import RunnerRouterMixin

HEADERS = {
    "host": "runner.internal",
    "x-api-key": "the-runner-token",
    "authorization": "Bearer something",
    "content-type": "application/json",
    "user-agent": "node",
}


class FakeRequest:

    def __init__(self, body):
        self.method = "POST"
        self.headers = dict(HEADERS)
        self.path_params: dict = {}
        self.query_params: dict = {}
        self._body = body

    async def json(self):
        return self._body


class Queue:

    def __init__(self, name: str, queued: list):
        self.name, self.queued = name, queued

    def add(self, item: str):
        self.queued.append((self.name, json.loads(item)))


def router(started: list, queued: list) -> type:
    """A stand-in for the router class the routes are bound to."""
    def start(self, **kwargs):
        started.append(kwargs)
        return {"runner_id": "r1"}

    return type("Router", (), {
        "runner_backend": SimpleNamespace(queue=lambda name: Queue(name, queued)),
        "runner_start": SimpleNamespace(_og=start),
    })


def post(route: str, cls: type, body: dict) -> dict:
    endpoint = RunnerRouterMixin.__dict__[route].__get__(None, cls)
    return asyncio.run(endpoint.function(FakeRequest(body)))


def test_execute_queues_the_callers_payload_and_none_of_its_headers():
    started: list = []
    queued: list = []
    body = {"queue_slug": "imge", "request_id": "req-1", "prompt": "a cat", "width": 1024}

    answer = post("runner_execute", router(started, queued), body)

    (queue_name, job), = queued
    assert queue_name == "req:imge"
    assert not set(HEADERS) & set(job), "an HTTP header was queued with the job"
    assert {key: job[key] for key in ("prompt", "width", "request_id")} == {
        "prompt": "a cat", "width": 1024, "request_id": "req-1",
    }
    assert answer["request_id"] == "req-1" and answer["queue_slug"] == "imge"
    assert started == []


def test_execute_starts_a_runner_from_start_configs_without_queueing_them():
    started: list = []
    queued: list = []
    start_configs = {"plugin": "RUNPOD", "runpod_serverless_id": "abc", "queue_slug": "imge"}
    body = {"queue_slug": "imge", "prompt": "a cat", "start_configs": start_configs}

    answer = post("runner_execute", router(started, queued), body)

    (_, job), = queued
    assert "start_configs" not in job, "the start settings were queued with the job"
    assert job["prompt"] == "a cat"
    assert started == [start_configs]
    assert answer["runner_start_output"] == {"runner_id": "r1"}


def test_a_payload_key_named_like_a_header_is_still_the_callers_to_send():
    queued: list = []

    post("runner_execute", router([], queued), {"queue_slug": "q", "host": "payload-value"})

    assert queued[0][1]["host"] == "payload-value"


def test_start_passes_no_header_to_the_runner_spec_or_the_plugin(monkeypatch):
    from fred.worker.runner.plugins import catalog as plugin_catalog
    received: dict = {}

    class Plugin:
        def execute(self, runner_spec, wait_for_exec=False, **kwargs):
            received["spec"] = runner_spec
            received["kwargs"] = kwargs
            return SimpleNamespace(runner_id="r1", future_exec=SimpleNamespace(future_id="f1"))

    monkeypatch.setattr(plugin_catalog, "PluginCatalog", {"RUNPOD": Plugin})
    body = {"plugin": "RUNPOD", "queue_slug": "imge", "runpod_serverless_id": "abc"}

    answer = post("runner_start", router([], []), body)

    assert answer == {"runner_id": "r1", "future_id": "f1", "queue_slug": "imge"}
    assert not set(HEADERS) & set(received["kwargs"]), "an HTTP header was passed to the plugin"
    assert "the-runner-token" not in repr(received["spec"]), "the API key reached the runner spec"
    assert received["kwargs"].get("runpod_serverless_id") == "abc"


def test_a_request_key_named_self_reaches_the_job_instead_of_breaking_the_route():
    # The route's arguments are the merged request; `self` is also the route's own first parameter.
    queued: list = []

    answer = post("runner_execute", router([], queued), {"queue_slug": "q", "self": "a payload value"})

    assert answer["queue_slug"] == "q"
    assert queued[0][1]["self"] == "a payload value"


def test_every_runner_route_takes_self_positionally_only():
    import inspect
    from fred.rest.router.endpoint import RouterEndpointAnnotation

    routes = {name: value for name, value in RunnerRouterMixin.__dict__.items()
              if isinstance(value, RouterEndpointAnnotation)}

    assert {"runner_start", "runner_execute", "runner_output", "qlen", "handler_exists"} <= set(routes)
    for name, route in routes.items():
        first = next(iter(inspect.signature(route.function).parameters.values()))
        assert first.kind is inspect.Parameter.POSITIONAL_ONLY, name
