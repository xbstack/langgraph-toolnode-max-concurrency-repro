# LangGraph ToolNode `max_concurrency` async reproduction

This repository-sized experiment reproduces a sync/async parity bug reported in LangGraph issue #8517.

## November 25, 2026: independent 1.2.22 follow-up

On macOS 27.0.1 arm64, Python 3.11.15, LangGraph 1.2.22, prebuilt 1.1.2 and core 1.5.3, the independent four-call matrix passed all 12 assertions. For caps 1/2/4, sync tools via `invoke` peaked at 1/2/4; both sync and async tools via `ainvoke` peaked at 4/4/4; the async-tool shared resource semaphore restored 1/2/4. All four result IDs and values were retained in every case. No real network, `create_agent` or thread cancellation test was performed. This confirms the specific single-ToolNode batch issue, not every agent scheduling architecture. See [machine-readable results](results/repro-1.2.22-20261125.json).

```sh
python3.11 -m venv .venv-1.2.22
.venv-1.2.22/bin/python -m pip install -r requirements-1.2.22.txt
.venv-1.2.22/bin/python repro_1_2_22.py
```

## Verified environment (original 1.2.10 study)

- macOS 26.5.2, Apple Silicon
- Python 3.11.15
- `langgraph==1.2.10`
- `langgraph-prebuilt==1.1.0`
- `langchain-core==1.5.3`
- `pytest==9.1.1`

## Result

Four tool calls were sent directly to one `ToolNode`.

| Execution path | `max_concurrency` | Measured `max_active` | Limit respected |
|---|---:|---:|---|
| sync `invoke()` | 1 | 1 | yes |
| async `ainvoke()` | 1 | 4 | no |
| sync `invoke()` | 2 | 2 | yes |
| async `ainvoke()` | 2 | 4 | no |
| sync `invoke()` | 4 | 4 | yes |
| async `ainvoke()` | 4 | 4 | yes, because the limit equals the tool count |

The installed source confirms the mismatch:

- `_func()` uses `get_executor_for_config(config)` and `executor.map(...)`.
- `_afunc()` builds every coroutine and calls `await asyncio.gather(*coros)`.
- LangChain Core already exposes `gather_with_concurrency(n, *coros)`.

This experiment is intentionally limited to direct multi-call `ToolNode` execution in a custom `StateGraph`. It does not claim that every agent architecture ignores the setting.

## Run

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python repro.py \
  --json-output results/repro-results.json \
  --text-output results/repro-results.txt
.venv/bin/python -m pytest -q
```

The reproduction command exits successfully when the current defect is observed. The test suite asserts both the current defect and the workaround behavior.

## Workaround

`workaround.py` wraps each asynchronous tool with a shared `asyncio.Semaphore`. The tests verify limits 1, 2, and 4, and verify that a permit is released when a tool raises an exception.

The workaround protects the bounded resource at the tool boundary. It is useful for rate-limited APIs, database pools, browser sessions, GPU slots, and non-concurrency-safe dependencies. It does not change LangGraph's internal scheduling and must be shared by all tools that consume the same constrained resource.

## Maintainer-level fix direction

A narrow parity change would replace the unconditional async gather with a bounded gather using `config.get("max_concurrency")`, then add sync/async regression tests. The upstream maintainers should decide the final implementation and compatibility behavior.

## Evidence

- Raw matrix: `results/repro-results.txt`
- Machine-readable matrix: `results/repro-results.json`
- Version matrix: `results/version-matrix.md`
- Tests: `tests/test_max_concurrency.py`
- Upstream issue: `https://github.com/langchain-ai/langgraph/issues/8517`

## XBSTACK articles

For the full reproduction analysis, scope notes, and production workaround:

- English: `https://www.xbstack.com/en/ai/langgraph-toolnode-max-concurrency-ignored/?utm_source=github&utm_medium=referral&utm_campaign=langgraph_toolnode_max_concurrency&utm_content=repository_readme`
- 中文：`https://www.xbstack.com/ai/langgraph-toolnode-max-concurrency-ignored/?utm_source=github&utm_medium=referral&utm_campaign=langgraph_toolnode_max_concurrency&utm_content=repository_readme`

Both pages document the same tested matrix and link back to upstream issue #8517.
