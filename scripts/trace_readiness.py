"""Verify local Phoenix persistence using independently authored synthetic spans."""
from __future__ import annotations


def check_trace(endpoint: str) -> str:
    """Export two synthetic spans and match their IDs and statuses on readback.

    Uses a private tracer provider, never the application's global provider. All
    optional SDK imports occur here so importing preflight remains lightweight.
    Network export and polling share a 15-second budget; no model or kit data is
    consulted. Failures expose checker-authored messages only.
    """
    import time
    from urllib.parse import urlsplit

    try:
        parsed = urlsplit(endpoint)
        if (parsed.scheme not in {"http", "https"}
                or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path.rstrip("/") not in {"", "/v1/traces"}):
            raise ValueError("invalid endpoint")
        base = f"{parsed.scheme}://{parsed.netloc}"

        import httpx
        import requests
        from opentelemetry.context import Context
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
        from opentelemetry.sdk.trace.sampling import ALWAYS_ON
        from opentelemetry.trace import Status, StatusCode
    except Exception:
        raise RuntimeError("Phoenix trace check requires a loopback endpoint and tracing dependencies") from None

    deadline = time.monotonic() + 15
    provider = None
    exporter = None
    try:
        project = "maintenance-readiness"
        provider = TracerProvider(
            resource=Resource({"service.name": "readiness-check", "openinference.project.name": project}),
            sampler=ALWAYS_ON,
            shutdown_on_exit=False,
        )
        captured = InMemorySpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(captured))
        tracer = provider.get_tracer("readiness.synthetic")
        with tracer.start_as_current_span("readiness.synthetic.success", context=Context()) as root:
            root.set_attribute("openinference.span.kind", "CHAIN")
            root.set_status(Status(StatusCode.OK))
            trace_id = f"{root.get_span_context().trace_id:032x}"
            root_id = f"{root.get_span_context().span_id:016x}"
            with tracer.start_as_current_span("readiness.synthetic.failed-tool") as child:
                child.set_attribute("openinference.span.kind", "TOOL")
                child.set_status(Status(StatusCode.ERROR, "Synthetic failure for readiness verification"))
                child_id = f"{child.get_span_context().span_id:016x}"

        # Disable proxy inheritance and redirects, keeping synthetic telemetry local.
        with requests.Session() as session:
            session.trust_env = False
            session.max_redirects = 0
            exporter = OTLPSpanExporter(
                endpoint=base + "/v1/traces",
                headers={"x-readiness-probe": "synthetic"},
                timeout=min(4.0, max(0.1, deadline - time.monotonic())),
                session=session,
            )
            if exporter.export(captured.get_finished_spans()) != SpanExportResult.SUCCESS:
                raise RuntimeError("export failed")

        expected = {root_id: "OK", child_id: "ERROR"}
        with httpx.Client(trust_env=False, follow_redirects=False) as client:
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                response = client.get(
                    f"{base}/v1/projects/{project}/traces",
                    params={"include_spans": "true", "limit": 100},
                    timeout=min(1.0, remaining),
                )
                if response.status_code == 200:
                    for trace in response.json().get("data", []):
                        if trace.get("trace_id") != trace_id:
                            continue
                        # This endpoint returns span summaries nested beneath
                        # their matching trace, with span_id at the top level.
                        actual = {
                            span["span_id"]: span["status_code"]
                            for span in trace.get("spans", [])
                        }
                        if all(actual.get(span_id) == status for span_id, status in expected.items()):
                            return f"Persisted trace {trace_id}; matched synthetic OK and ERROR span IDs"
                elif response.status_code != 404:
                    raise RuntimeError("readback rejected")
                time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
        raise RuntimeError("readback deadline exceeded")
    except Exception:
        raise RuntimeError("Phoenix synthetic trace export/readback failed within the 15-second budget") from None
    finally:
        if exporter is not None:
            exporter.shutdown()
        if provider is not None:
            provider.shutdown()
