import json
import subprocess
import model


def test_escalates_timeout_then_succeeds():
    seen = []

    def fake(argv, env, input_text, timeout):
        seen.append(timeout)
        if len(seen) == 1:
            raise subprocess.TimeoutExpired(cmd="claude", timeout=timeout)
        return json.dumps({"themes": [{"slug": "x"}]})

    retries = []
    out = model.call_model("P", {}, "m", timeout=100, runner=fake,
                           max_retries=1, on_retry=lambda nt: retries.append(nt))
    assert out["themes"][0]["slug"] == "x"
    assert seen == [100, 200]                 # retried with doubled timeout
    assert retries == [200]


def test_timeout_exhausts_retries_then_raises():
    def fake(argv, env, input_text, timeout):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=timeout)

    try:
        model.call_model("P", {}, "m", timeout=100, runner=fake, max_retries=1)
        assert False, "expected ModelError"
    except model.ModelError:
        pass


def test_non_timeout_error_is_not_retried():
    seen = []

    def fake(argv, env, input_text, timeout):
        seen.append(timeout)
        raise model.ModelError("auth bad")     # not a timeout

    try:
        model.call_model("P", {}, "m", timeout=100, runner=fake, max_retries=1)
        assert False, "expected ModelError"
    except model.ModelError:
        pass
    assert len(seen) == 1                       # NOT retried


def test_build_argv_has_guards():
    argv, env = model._build_invocation("PROMPT", {"type": "object"},
                                        "claude-haiku-4-5")
    assert argv[0] == "claude"
    assert "-p" in argv
    assert "PROMPT" in argv                 # prompt passed as positional arg, not stdin
    assert "--output-format" in argv        # required for --json-schema to take effect
    assert "--json-schema" in argv
    assert "--tools" in argv
    assert env["LAYERED_MEMORY_INTERNAL"] == "1"


def test_call_model_parses_bare_object_via_fake():
    def fake_run(argv, env, input_text, timeout):
        return json.dumps({"themes": [{"slug": "x"}]})
    out = model.call_model("PROMPT", {"type": "object"}, "claude-haiku-4-5",
                           timeout=5, runner=fake_run)
    assert out["themes"][0]["slug"] == "x"


def test_call_model_unwraps_cc_envelope_structured_output():
    def fake_run(argv, env, input_text, timeout):
        return json.dumps({"type": "result", "result": "",
                           "structured_output": {"themes": [{"slug": "y"}]}})
    out = model.call_model("PROMPT", {"type": "object"}, "claude-haiku-4-5",
                           timeout=5, runner=fake_run)
    assert out["themes"][0]["slug"] == "y"


def test_call_model_envelope_without_structured_output_raises():
    def fake_run(argv, env, input_text, timeout):
        return json.dumps({"type": "result", "result": "prose, no schema",
                           "structured_output": None})
    try:
        model.call_model("P", {}, "m", timeout=5, runner=fake_run)
        assert False, "expected ModelError"
    except model.ModelError:
        pass


def test_call_model_raises_on_bad_json():
    def fake_run(argv, env, input_text, timeout):
        return "not json at all"
    try:
        model.call_model("P", {}, "m", timeout=5, runner=fake_run)
        assert False, "expected ModelError"
    except model.ModelError:
        pass


def test_leading_dash_prompt_is_guarded():
    argv, _ = model._build_invocation("---\nname: skill\n# body", {}, "m")
    # the prompt must not appear as a bare leading-dash positional
    assert "---\nname: skill\n# body" not in argv
    assert " ---\nname: skill\n# body" in argv     # space-prefixed, defused


def test_recursion_guard_short_circuits(monkeypatch):
    monkeypatch.setenv("LAYERED_MEMORY_INTERNAL", "1")
    assert model.is_internal_call() is True
