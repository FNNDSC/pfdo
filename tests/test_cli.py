"""Tests for the pfdo command line."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pfdo import __version__
from pfdo.__main__ import CLI_DS, CLI_FULL, main, manual_build, parser_build, synopsis


def tree_make(root: Path) -> tuple[Path, Path]:
    inputDir: Path = root / "in"
    outputDir: Path = root / "out"
    (inputDir / "s").mkdir(parents=True)
    (inputDir / "s/x.jpg").touch()
    (inputDir / "s/y.txt").touch()
    return inputDir, outputDir


def test_main_jsonPrintsTree(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    inputDir, outputDir = tree_make(tmp_path)
    code: int = main(["--inputDir", str(inputDir), "--outputDir", str(outputDir), "--relativeDir", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tree"] == {"s": ["x.jpg", "y.txt"]}
    assert payload["process"] is None


def test_main_testTouchesAnalyzedFiles(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    inputDir, outputDir = tree_make(tmp_path)
    code: int = main(
        [
            "--inputDir",
            str(inputDir),
            "--outputDir",
            str(outputDir),
            "--fileFilter",
            "jpg",
            "--test",
            "--json",
            "--printElapsedTime",
            "--verbosity",
            "0",
        ]
    )
    assert code == 0
    out: str = capsys.readouterr().out
    assert (outputDir / "s/analyzed-x.jpg").exists()
    assert not (outputDir / "s/analyzed-y.txt").exists()
    assert "Elapsed time" in out


def test_main_badIndexIsUsageError(tmp_path: Path) -> None:
    inputDir, outputDir = tree_make(tmp_path)
    with pytest.raises(SystemExit) as exc:
        main(["--inputDir", str(inputDir), "--outputDir", str(outputDir), "--analyzeFileIndex", "q"])
    assert exc.value.code == 2


def test_main_inputDirRequired() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--test"])
    assert exc.value.code == 2


def test_main_versionAndManual(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out
    with pytest.raises(SystemExit) as exc:
        main(["--man"])
    assert exc.value.code == 0
    out: str = capsys.readouterr().out
    assert "Path-File Do (something)" in out
    assert "[--analyzeFileIndex <a|f|l|m|N>]" in out
    assert "[--fileFilter <token1,token2,...>]" in out
    assert "EXAMPLES" in out
    assert "``" not in out
    with pytest.raises(SystemExit) as exc:
        main(["--synopsis"])
    assert exc.value.code == 0
    assert "DESCRIPTION" not in capsys.readouterr().out


def test_synopsis_takesAnotherCommandName() -> None:
    text: str = synopsis(shortOnly=True, command="pfdo_run")
    assert "pfdo_run \\" in text
    assert CLI_FULL in text
    assert "<inputDir>" in CLI_DS and "--inputDir" not in CLI_DS
    assert manual_build().command == "pfdo"


def test_parser_build_dsOmitsIoArguments() -> None:
    dsStyle = parser_build(standalone=False)
    with pytest.raises(SystemExit):
        dsStyle.parse_args(["--inputDir", "x"])
    args = dsStyle.parse_args(["--analyzeFileIndex", "m", "--test"])
    assert args.analyzeFileIndex == "m" and args.testRun is True


def test_parser_dsStyleManNeedsNoDirectories(capsys: pytest.CaptureFixture[str]) -> None:
    parser = parser_build(standalone=False, command="pfdo_x")
    parser.add_argument("inputdir")
    parser.add_argument("outputdir")
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--man"])
    assert exc.value.code == 0
    assert "Path-File Do (something)" in capsys.readouterr().out
