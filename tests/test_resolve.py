import resolve


def _fp(repos=None, written=None, reads=None, symbols=None, skills=None, tickets=None):
    return {
        "repos": repos or [],
        "files_written": {r: paths for r, paths in (written or {}).items()},
        "files_read": reads or {},
        "symbols": {s: 2 for s in (symbols or [])},
        "skills_used": skills or [],
        "tickets": tickets or [],
    }


def _mk(repos=None, written=None, reads_recurring=None, symbols=None, skills=None,
        tickets=None, keywords=None):
    # a match_keys-shaped note entry
    return {
        "repos": repos or [],
        "files_written": written or [],
        "files_read_recurring": reads_recurring or [],
        "symbols": symbols or [],
        "skills_used": skills or [],
        "tickets": tickets or [],
        "keywords": keywords or [],
    }


def test_ticket_dominates():
    sk = {"tickets": ["GOVFOUN-438"], "repos": [], "files_written": [],
          "files_read_recurring": [], "symbols": [], "skills_used": []}
    nk = _mk(tickets=["GOVFOUN-438"])
    assert resolve.score(sk, nk) >= resolve.W_TICKET


def test_written_file_overlap_scored():
    sk = {"files_written": ["heracles/store/a.go", "atlas/b.java"], "repos": [],
          "files_read_recurring": [], "symbols": [], "skills_used": [], "tickets": []}
    nk = _mk(written=["heracles/store/a.go"])
    assert resolve.score(sk, nk) == resolve.W_FILE_WRITTEN


def test_candidates_ranked_and_filtered():
    db = {
        "feat-a": _mk(written=["r/x.go"], repos=["r"]),
        "feat-b": _mk(repos=["r"]),
        "feat-unrelated": _mk(repos=["zzz"]),
    }
    session = _fp(repos=["r"], written={"r": ["x.go"]})
    cands = resolve.candidates(session, db)
    slugs = [s for s, _ in cands]
    assert slugs[0] == "feat-a"               # written-overlap wins
    assert "feat-unrelated" not in slugs      # zero score filtered


def test_decide_ticket_is_confident_match():
    db = {"feat-a": _mk(tickets=["G-1"], repos=["r"])}
    session = _fp(tickets=["G-1"])
    assert resolve.decide(session, db) == ("match", "feat-a")


def test_decide_no_signal_is_new():
    db = {"feat-a": _mk(repos=["other-repo"])}
    session = _fp(repos=["mine"], written={"mine": ["a.go"]})
    assert resolve.decide(session, db) == ("new", None)


def test_decide_repo_only_is_new_not_ambiguous():
    # shared repo only = score 2 < AMBIGUOUS_MIN(4) → new (don't burn an LLM tiebreak)
    db = {"feat-a": _mk(repos=["r"])}
    session = _fp(repos=["r"])
    assert resolve.decide(session, db) == ("new", None)


def test_decide_mid_signal_is_ambiguous():
    # two shared repos = score 4 = AMBIGUOUS_MIN → genuine middle → tiebreak
    db = {"feat-a": _mk(repos=["r1", "r2"])}
    session = _fp(repos=["r1", "r2"])
    kind, payload = resolve.decide(session, db)
    assert kind == "ambiguous" and "feat-a" in payload


def test_keyword_overlap_scored():
    a = _mk(keywords=["x", "y"])
    b = _mk(keywords=["x", "z"])
    assert resolve.score(a, b) == resolve.W_KEYWORD          # one shared keyword


def test_keyword_jaccard():
    a = {"keywords": ["x", "y", "z"]}
    b = {"keywords": ["x", "y", "w"]}
    assert resolve.keyword_jaccard(a, b) == 2 / 4            # {x,y} / {x,y,z,w}
    assert resolve.keyword_jaccard({"keywords": []}, b) == 0.0


def test_llm_tiebreak_returns_valid_choice():
    def caller(p, s, m, t):
        return {"choice": "feat-a"}
    out = resolve.llm_tiebreak("did X", [("feat-a", "about a"), ("feat-b", "about b")],
                               model_caller=caller)
    assert out == "feat-a"


def test_llm_tiebreak_invalid_choice_falls_back_to_new():
    def caller(p, s, m, t):
        return {"choice": "something-made-up"}
    out = resolve.llm_tiebreak("did X", [("feat-a", "a")], model_caller=caller)
    assert out == "new"


def test_llm_tiebreak_error_is_new():
    def caller(p, s, m, t):
        raise RuntimeError("boom")
    assert resolve.llm_tiebreak("x", [("feat-a", "a")], model_caller=caller) == "new"
