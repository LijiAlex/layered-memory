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
    argv = [
        "claude", "-p",
        "--model", model,
        "--tools", "",                         # no tools: pure text compression
        "--json-schema", json.dumps(schema),
    ]
    env = dict(os.environ)
    env["LAYERED_MEMORY_INTERNAL"] = "1"        # PRIMARY recursion guard
    return argv, env


def _default_runner(argv, env, input_text, timeout):
    proc = subprocess.run(
        argv, input=input_text, env=env, timeout=timeout,
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise ModelError(f"claude exited {proc.returncode}: {proc.stderr[:500]}")
    return proc.stdout


def call_model(prompt: str, schema: dict, model: str, timeout: int,
               runner=_default_runner) -> dict:
    argv, env = _build_invocation(prompt, schema, model)
    raw = runner(argv, env, prompt, timeout)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ModelError(f"model output was not JSON: {raw[:500]}") from e
