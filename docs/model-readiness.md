# Local model readiness

Validated 2026-10-21 on Windows, Ollama 0.40.7 and an NVIDIA RTX 3080
(10 GB VRAM). All inference used newly written arithmetic prompts and a
local `multiply` tool. No supplied kit data or manuals were sent to a model.

## Primary: Gemma 4 12B

Installed source: `gemma4:12b` (Q4_K_M), digest
`6114515d63c17436a7c0417d82820ac65ad643e2806c5a3c89cb62846436ed0b`.
The model advertises tools and thinking, with thinking enabled by default.

Create the local alias from the repository root:

```powershell
ollama create maintenance-gemma4:12b -f scripts/models/gemma4.Modelfile
```

The alias reuses the installed weights, sets a 4,096-token context, and does
not change global Ollama settings. Use `LLM_MODEL=maintenance-gemma4:12b`,
`LLM_BASE_URL=http://localhost:11434/v1`, and the local placeholder key
`LLM_API_KEY=ollama`.

Verified client configuration:

```python
ChatOpenAI(
    model="maintenance-gemma4:12b",
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    temperature=0.1,
    reasoning_effort="none",
    max_tokens=256,
    timeout=60,
    max_retries=0,
)
```

Bind the tool schema, invoke the model, execute the returned tool locally,
append the assistant message and a `ToolMessage` with its matching call ID,
and invoke again. Tests verified the parsed numeric arguments and the final
answer, rather than merely accepting HTTP 200.

| Check | Tool call | Final answer | Total |
| --- | ---: | ---: | ---: |
| Native `/api/chat`, initially unloaded, `think=false`, `num_ctx=4096` | 19.06 s | 2.70 s | 21.76 s |
| LangChain `/v1`, alias using already loaded weights | 2.596 s | 0.225 s | 2.821 s |
| LangChain `/v1`, warm | 0.226 s | 0.213 s | 0.439 s |
| LangChain `/v1`, unloaded immediately before test | 7.933 s | 0.190 s | 8.124 s |

An additional `/v1` tool request without `reasoning_effort` passed in
2.682 seconds. This permits the supplied smoke test to select the alias via
an environment override without modifying the supplied script. Explicitly
disable thinking in the application to keep latency and token use bounded.
The fixed context plus disabled thinking resolved the earlier timeout in
these checks; they do not establish which setting alone caused it.

The 256-token generation cap is a readiness-test setting, not an acceptance
criterion for a full application answer. Set appropriate output and total
agent budgets during implementation. Account for the 4,096-token context
when limiting retrieved evidence. Serialize GPU inference during local
integration; a simple arithmetic check does not validate maintenance-answer
quality or establish a latency guarantee for longer prompts.

## Fallback: Llama 3.2 3B

Pulled `llama3.2:3b` (2,019,393,189 bytes), source digest
`a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72`.
The model advertises completion and tools; its thinking metadata permits
only `false`. Create the alias:

```powershell
ollama pull llama3.2:3b
ollama create maintenance-llama32:3b -f scripts/models/llama32.Modelfile
```

Use `LLM_FALLBACK_MODEL=maintenance-llama32:3b`, temperature `0`, the same
local `/v1` endpoint, a 60-second request timeout and no automatic client
retries. Omit `reasoning_effort` for this non-thinking model. Return tool
results as JSON and explicitly instruct the model to copy authoritative
values unchanged rather than recompute them.

For a machine-validated final response, invoke a final client without bound
tools and with `response_format={"type": "json_object"}` after appending the
assistant tool-call message and corresponding `ToolMessage`. Validate parsed
JSON equality, not a substring such as `ready` that also matches `not-ready`.
The initial prompt-only test calculated the correct value but answered in
prose despite a JSON instruction; JSON response mode resolved that format
failure.

Three real LangChain `/v1` tool/result/final tests returned exactly
`{"result": 391}`, `{"result": 377}` and `{"result": 513}`. Loaded totals
were 2.567, 0.172 and 0.171 seconds. Two more tests copied opaque `status`
values `ready` and `not-ready` exactly (0.157 and 5.588 seconds). A test after
unloading the model returned exact `{"status":"ready"}` in 4.226 seconds
(tool call 4.153 seconds, final answer 0.074 seconds).

These checks establish basic interface readiness, not maintenance-answer
quality. Broader factual and citation acceptance tests remain required.

A larger newly downloaded Ministral candidate was replaced to conserve disk;
only the two candidate model names created during setup were removed. The
preexisting Gemma and Hermes models were preserved. Free space measured
19,936,993,280 bytes after replacement, approximately 63 MB short of a strict
20-billion-byte target. The coordinator then removed 319 MB of regenerable
Python bytecode caches whose corresponding source files exist, restoring
approximately 20.32 GB free. Startup uses `-B` to avoid immediately rebuilding
those caches. Preflight enforces 20 billion free bytes; recheck before execution.

## Existing Hermes model

The installed `hf.co/NousResearch/Hermes-3-Llama-3.1-8B-GGUF:Q4_K_M`
advertises only `completion`. A real `/v1` request containing tools returned
HTTP 400: `does not support tools`. Do not list this particular installed
artifact as a verified tool-calling fallback. It was not modified or deleted.

## Official references

- [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility):
  `reasoning_effort="none"` disables thinking; custom context size is set
  through a model alias rather than a standard OpenAI request parameter.
- [Ollama thinking controls](https://docs.ollama.com/capabilities/thinking):
  `/api/show` reports supported values and their default.
- [Ollama model creation](https://docs.ollama.com/api/create): local aliases
  inherit an existing model and override parameters.
- [Llama 3.2 3B](https://ollama.com/library/llama3.2:3b): an approximately
  2 GB official model with tool support.
