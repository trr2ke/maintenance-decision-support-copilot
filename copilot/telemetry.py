"""Local traces contain operation status, never evidence or model prompts."""
from contextlib import contextmanager

_provider = None
_session = None


def configure_tracing():
    global _provider, _session
    if _provider is not None:
        return _provider
    import requests
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from copilot.config import get_settings

    _session = requests.Session()
    _session.trust_env = False
    _session.max_redirects = 0
    endpoint = get_settings().phoenix_collector_endpoint.rstrip("/")
    if not endpoint.endswith("/v1/traces"):
        endpoint += "/v1/traces"
    provider = TracerProvider(resource=Resource({
        "service.name": "maintenance-copilot",
        "openinference.project.name": "maintenance-copilot",
    }))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
        endpoint=endpoint, timeout=3, session=_session,
    )))
    _provider = provider
    return provider


@contextmanager
def trace_operation(name):
    from opentelemetry.trace import Status, StatusCode
    provider = configure_tracing()
    tracer = provider.get_tracer("copilot.operations")
    with tracer.start_as_current_span(name, record_exception=False, set_status_on_exception=False) as span:
        try:
            yield span
        except Exception:
            span.set_status(Status(StatusCode.ERROR, "Operation failed"))
            raise


def flush_traces():
    if _provider is not None:
        _provider.force_flush(timeout_millis=4000)
