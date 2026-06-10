"""The model-call seam: subprocess `claude -p` with recursion guard (spec §8.2).
Stdlib only. The `runner` arg is injectable for tests."""
import os
import json
import subprocess


class ModelError(Exception):
    pass


def is_internal_call() -> bool:
    """Hooks call this first and exit if True (recursion guard)."""
    return os.environ.get("LAYERED_MEMORY_INTERNAL") == "1"


def _build_invocation(prompt: str, schema: dict, model: str):
    # Prompt is passed as a POSITIONAL arg (not stdin) — stdin was out-weighed by
    # ambient context and the model ignored it (verified empirically). `--output-format
    # json` is REQUIRED for `--json-schema` to take effect; the schema-conforming object
    # then arrives in the envelope's `structured_output` field (not `result`).
    # NOTE: `--bare` is intentionally NOT used — it ignores OAuth/keychain auth and
    # fails ("Not logged in") for subscription users (verified). The recursion env-guard
    # below is the isolation mechanism instead.
    # Guard: a positional prompt that begins with '-' is misparsed as a CLI option.
    safe_prompt = prompt if not prompt.startswith("-") else " " + prompt
    argv = [
        "claude", "-p", safe_prompt,
        "--model", model,
        "--output-format", "json",
        "--tools", "",                         # no tools: pure text compression
        "--json-schema", json.dumps(schema),
    ]
    env = dict(os.environ)
    env["LAYERED_MEMORY_INTERNAL"] = "1"        # PRIMARY recursion guard
    return argv, env


def _default_runner(argv, env, input_text, timeout):
    import tempfile
    proc = subprocess.run(
        argv, input=input_text, env=env, timeout=timeout,
        capture_output=True, text=True,
        cwd=tempfile.gettempdir(),             # avoid loading a project CLAUDE.md
    )
    if proc.returncode != 0:
        raise ModelError(f"claude exited {proc.returncode}: {proc.stderr[:500]}")
    return proc.stdout


def call_model(prompt: str, schema: dict, model: str, timeout: int,
               runner=_default_runner, max_retries: int = 0, on_retry=None) -> dict:
    """Call the model and return the schema-conforming object.

    On a TIMEOUT (subprocess.TimeoutExpired) the call is retried with double the timeout,
    up to `max_retries` times — so a borderline-slow call usually finishes in this pass.
    Non-timeout errors (auth, bad JSON, nonzero exit) are NOT retried (more time won't help).
    `on_retry(new_timeout)` is called before each retry (for progress logging).

    Handles three shapes of `raw`:
    - CC envelope with `structured_output` (real `claude -p --output-format json`) → unwrap it.
    - CC envelope present but no `structured_output` → ModelError.
    - bare object (unit-test fakes / direct schema dict) → returned as-is.
    """
    argv, env = _build_invocation(prompt, schema, model)
    attempt_timeout = timeout
    attempts = max_retries + 1
    raw = None
    for i in range(attempts):
        try:
            raw = runner(argv, env, "", attempt_timeout)   # prompt is in argv; stdin empty
            break
        except subprocess.TimeoutExpired:
            if i == attempts - 1:
                raise ModelError(f"timed out after {attempts} attempt(s) "
                                 f"(final {attempt_timeout}s)")
            attempt_timeout *= 2
            if on_retry:
                on_retry(attempt_timeout)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ModelError(f"model output was not JSON: {raw[:500]}") from e
    if isinstance(obj, dict) and obj.get("structured_output") is not None:
        return obj["structured_output"]
    if isinstance(obj, dict) and ("structured_output" in obj or obj.get("type") == "result"):
        raise ModelError(f"no structured_output in CC envelope: {raw[:400]}")
    return obj
