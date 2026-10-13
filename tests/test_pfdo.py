"""Tests for the Pfdo base class and the file-index rule."""

from __future__ import annotations

from pathlib import Path

import pytest
from pftree.models import DirNode, StageResult

from pfdo.models import PfdoOptions, fileIndex_validate
from pfdo.pfdo import ANALYZED_PREFIX, Pfdo, fileIndex_select

FILES: list[str] = ["a", "b", "c", "d", "e"]


def tree_make(root: Path) -> tuple[Path, Path]:
    """The fixture of the 5.x test: two subjects, mgz and txt files."""
    inputDir: Path = root / "incoming"
    outputDir: Path = root / "outgoing"
    for rel, names in {
        "A/a": ["aseg.mgz", "aseg+aparc.mgz", "aseg2009+aparc.mgz", "aseg2009.txt"],
        "B/b": ["mri.mgz", "mri+aparc.mgz", "aseg2009+mri.mgz", "mri.txt"],
    }.items():
        (inputDir / rel).mkdir(parents=True)
        for name in names:
            (inputDir / rel / name).touch()
    outputDir.mkdir()
    return inputDir, outputDir


def options_make(inputDir: Path, outputDir: Path, **extra: object) -> PfdoOptions:
    values: dict[str, object] = {
        "inputDir": inputDir,
        "outputDir": outputDir,
        "verbosity": 0,
        "relativeDir": True,
    }
    values.update(extra)
    return PfdoOptions.fromDict(values)


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("a", FILES),
        ("f", ["a"]),
        ("l", ["e"]),
        ("m", ["c"]),
        ("0", ["a"]),
        ("4", ["e"]),
        ("5", ["a"]),
        ("12", ["c"]),
        ("-1", ["e"]),
        ("-5", ["a"]),
        ("-6", ["e"]),
    ],
)
def test_fileIndex_select(spec: str, expected: list[str]) -> None:
    assert fileIndex_select(FILES, spec) == expected


def test_fileIndex_select_middleOfEvenAndOdd() -> None:
    assert fileIndex_select(["a", "b", "c"], "m") == ["b"]
    assert fileIndex_select(["a", "b", "c", "d"], "m") == ["c"]
    assert fileIndex_select(["only"], "m") == ["only"]


def test_fileIndex_select_emptyAndBad() -> None:
    assert fileIndex_select([], "f") == []
    with pytest.raises(ValueError, match="analyzeFileIndex"):
        fileIndex_select(FILES, "x")


def test_fileIndex_validate() -> None:
    for spec in ("a", "f", "l", "m", "0", "-3", "42"):
        fileIndex_validate(spec)
    with pytest.raises(ValueError, match="analyzeFileIndex"):
        fileIndex_validate("middle")


def test_options_rejectBadIndex(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="analyzeFileIndex"):
        PfdoOptions(inputDir=tmp_path, analyzeFileIndex="z")


def test_run_withoutTestOnlyProbes(tmp_path: Path) -> None:
    inputDir, outputDir = tree_make(tmp_path)
    result = Pfdo(options_make(inputDir, outputDir)).run()
    assert result.status
    assert set(result.tree) == {"A/a", "B/b"}
    assert result.process is None
    assert not any(outputDir.iterdir())


def test_testRun_reproducesTheFiveXTest(tmp_path: Path) -> None:
    inputDir, outputDir = tree_make(tmp_path)
    options: PfdoOptions = options_make(
        inputDir, outputDir, testRun=True, fileFilter="aparc,mgz", fileFilterLogic="AND"
    )
    result = Pfdo(options).run()
    assert result.status
    assert result.process is not None
    assert result.process.filesSaved == 3
    for rel in (
        "A/a/analyzed-aseg+aparc.mgz",
        "A/a/analyzed-aseg2009+aparc.mgz",
        "B/b/analyzed-mri+aparc.mgz",
    ):
        assert (outputDir / rel).exists()
    assert not (outputDir / "A/a/analyzed-aseg.mgz").exists()


def test_testRun_fileIndexMiddle(tmp_path: Path) -> None:
    inputDir, outputDir = tree_make(tmp_path)
    result = Pfdo(options_make(inputDir, outputDir, testRun=True, analyzeFileIndex="m")).run()
    assert result.status
    written: set[str] = {p.name for p in (outputDir / "A/a").iterdir()}
    assert written == {
        ANALYZED_PREFIX + sorted(["aseg.mgz", "aseg+aparc.mgz", "aseg2009+aparc.mgz", "aseg2009.txt"])[2]
    }


def test_testRun_existingOutputNeedsOverwrite(tmp_path: Path) -> None:
    inputDir, outputDir = tree_make(tmp_path)
    assert Pfdo(options_make(inputDir, outputDir, testRun=True)).run().status
    again = Pfdo(options_make(inputDir, outputDir, testRun=True)).run()
    assert not again.status
    assert again.process is not None
    assert all(not result.status for result in again.process.write.values())
    forced = Pfdo(options_make(inputDir, outputDir, testRun=True, overwrite=True)).run()
    assert forced.status


def test_outputLeafDirAppliesToSavedTree(tmp_path: Path) -> None:
    inputDir, outputDir = tree_make(tmp_path)
    result = Pfdo(options_make(inputDir, outputDir, testRun=True, outputLeafDir="done-%s")).run()
    assert result.status
    assert (outputDir / "A/done-a/analyzed-aseg.mgz").exists()


class Counter(Pfdo):
    """A subclass that always processes and writes one count file per directory."""

    processAlways = True

    def inputAnalyze_callback(self, node: DirNode, read: StageResult) -> StageResult:
        return StageResult(status=True, files=self.filesToAnalyze(node), payload={"count": len(node.files)})

    def outputSave_callback(self, node: DirNode, analyze: StageResult) -> StageResult:
        node.outputPath.mkdir(parents=True, exist_ok=True)
        (node.outputPath / "count.txt").write_text(f"{analyze.payload['count']}\n")
        return StageResult(status=True, files=["count.txt"])


def test_subclass_processAlways(tmp_path: Path) -> None:
    inputDir, outputDir = tree_make(tmp_path)
    result = Counter(options_make(inputDir, outputDir, analyzeFileIndex="f")).run()
    assert result.status
    assert result.process is not None
    assert result.process.filesAnalyzed == 2
    assert (outputDir / "A/a/count.txt").read_text() == "4\n"


def test_run_missingInputDir(tmp_path: Path) -> None:
    result = Pfdo(options_make(tmp_path / "nope", tmp_path / "out")).run()
    assert not result.status
    assert "not found" in result.error
