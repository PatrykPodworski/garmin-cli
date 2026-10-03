import pytest

from garmin_cli.cli import main


def test_help_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["--help"])

    assert exit.value.code == 0
    assert "usage: garmin" in capsys.readouterr().out


@pytest.mark.parametrize(
    "command", ["activities", "activity", "sleep", "stats", "weight", "bp"]
)
def test_raw_help_on_every_data_command(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main([command, "--help"])

    help_text = " ".join(capsys.readouterr().out.split())
    assert "--raw print the full Garmin response" in help_text
