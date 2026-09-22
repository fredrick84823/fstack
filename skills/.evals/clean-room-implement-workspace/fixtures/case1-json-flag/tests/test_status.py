from mytool.cli import main


def test_status_human_output(capsys):
    assert main(["status", "--root", "/tmp/demo"]) == 0
    out = capsys.readouterr().out
    assert "root:     /tmp/demo" in out
    assert "state:    dirty" in out
