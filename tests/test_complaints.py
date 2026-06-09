import complaints
import paths


def test_log_complaint_appends_row(tmp_path):
    complaints.log_complaint(tmp_path, wrong="tool-patterns",
                             right="connectors", gist="which connectors exist")
    text = paths.complaints_path(tmp_path).read_text()
    assert "tool-patterns" in text
    assert "connectors" in text
    assert "which connectors exist" in text


def test_log_complaint_appends_not_overwrites(tmp_path):
    complaints.log_complaint(tmp_path, "a", "b", "g1")
    complaints.log_complaint(tmp_path, "c", "d", "g2")
    lines = [l for l in paths.complaints_path(tmp_path).read_text().splitlines()
             if l.strip() and not l.startswith("#")]
    assert len(lines) == 2


def test_log_complaint_sanitizes_pipes(tmp_path):
    # the gist must not break the pipe-delimited row format
    complaints.log_complaint(tmp_path, "a", "b", "has | pipe | chars")
    lines = [l for l in paths.complaints_path(tmp_path).read_text().splitlines()
             if l.strip() and not l.startswith("#")]
    assert len(lines[0].split("|")) == 4    # wrong | right | gist | ts
