import json
import model


def test_build_argv_has_guards():
    argv, env = model._build_invocation("PROMPT", {"type": "object"},
                                        "claude-haiku-4-5")
    assert argv[0] == "claude"
    assert "-p" in argv
    assert "--json-schema" in argv
    assert "--tools" in argv
    assert env["LAYERED_MEMORY_INTERNAL"] == "1"


def test_call_model_parses_json_via_fake():
    def fake_run(argv, env, input_text, timeout):
        return json.dumps({"themes": [{"slug": "x"}]})
    out = model.call_model("PROMPT", {"type": "object"}, "claude-haiku-4-5",
                           timeout=5, runner=fake_run)
    assert out["themes"][0]["slug"] == "x"


def test_call_model_raises_on_bad_json():
    def fake_run(argv, env, input_text, timeout):
        return "not json at all"
    try:
        model.call_model("P", {}, "m", timeout=5, runner=fake_run)
        assert False, "expected ModelError"
    except model.ModelError:
        pass


def test_recursion_guard_short_circuits(monkeypatch):
    monkeypatch.setenv("LAYERED_MEMORY_INTERNAL", "1")
    assert model.is_internal_call() is True
