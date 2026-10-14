"""Tool and analyze: a task attached by decorator runs through the same frame as a subclass."""

from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path

import pytest

from pfdo import Pfdo, PfdoOptions, Tool, analyze
from pfdo.models import DirNode, RunResult, StageResult
from pfdo.tool import PLUGIN_SIGNATURE


def tree_make(root: Path) -> tuple[Path, Path]:
    inputDir: Path = root / "incoming"
    outputDir: Path = root / "outgoing"
    for rel, names in {"a": ["one.jpg", "two.jpg", "note.txt"], "b/c": ["three.jpg"]}.items():
        (inputDir / rel).mkdir(parents=True)
        for name in names:
            (inputDir / rel / name).write_text(name)
    outputDir.mkdir()
    return inputDir, outputDir


def copy_toPng(node: DirNode, read: StageResult) -> StageResult:
    for name in read.files:
        (node.outputPath / Path(name).with_suffix(".png")).write_text((node.path / name).read_text())
    return StageResult(status=True, files=read.files)


class JpgToPng(Pfdo):
    def inputAnalyze_callback(self, node: DirNode, read: StageResult) -> StageResult:
        node.outputPath.mkdir(parents=True, exist_ok=True)
        chosen: list[str] = self.filesToAnalyze(node)
        return copy_toPng(node, StageResult(status=bool(chosen), files=chosen))


def test_decorator_matchesSubclass(tmp_path: Path) -> None:
    inputDir, outputDir = tree_make(tmp_path)
    decorated = analyze(fileFilter="glob:*.jpg", verbosity=0)
    tool: Tool = decorated(copy_toPng)
    byTool: RunResult = tool(inputDir, outputDir)
    outputs: list[str] = sorted(str(p.relative_to(outputDir)) for p in outputDir.rglob("*.png"))
    assert outputs == ["a/one.png", "a/two.png", "b/c/three.png"]

    other: Path = tmp_path / "other"
    other.mkdir()
    bySubclass: RunResult = JpgToPng(
        PfdoOptions(inputDir=inputDir, outputDir=other, fileFilter="glob:*.jpg", verbosity=0)
    ).run()
    assert byTool.status is bySubclass.status is True
    assert byTool.process is not None and bySubclass.process is not None
    assert sorted(byTool.process.analyze) == sorted(bySubclass.process.analyze)
    assert sorted(str(p.relative_to(other)) for p in other.rglob("*.png")) == outputs


def test_tool_isNamedAfterFunction_andCarriesPluginSignature() -> None:
    tool: Tool = analyze(fileFilter="jpg")(copy_toPng)
    assert tool.name == "copy_toPng" and tool.__name__ == "copy_toPng"
    assert inspect.signature(tool) == PLUGIN_SIGNATURE
    params = list(inspect.signature(tool).parameters.values())
    assert params[0].annotation is argparse.Namespace and params[1].annotation is Path


def test_readFiles_honourAnalyzeFileIndex(tmp_path: Path) -> None:
    inputDir, outputDir = tree_make(tmp_path)
    seen: dict[str, list[str]] = {}

    @analyze(fileFilter="glob:*.jpg", analyzeFileIndex="f", verbosity=0)
    def first_only(node: DirNode, read: StageResult) -> StageResult:
        seen[node.relPath] = list(read.files)
        assert node.outputPath.is_dir()
        return StageResult(status=True, files=read.files)

    assert first_only(inputDir, outputDir).status is True
    assert seen == {"a": ["one.jpg"], "b/c": ["three.jpg"]}


def test_run_overrides_beatDefaults(tmp_path: Path) -> None:
    inputDir, outputDir = tree_make(tmp_path)
    seen: list[str] = []

    @analyze(fileFilter="glob:*.jpg", analyzeFileIndex="f", verbosity=0)
    def which(node: DirNode, read: StageResult) -> StageResult:
        seen.extend(read.files)
        return StageResult(status=True, files=read.files)

    which(inputDir, outputDir, analyzeFileIndex="a")
    assert sorted(seen) == ["one.jpg", "three.jpg", "two.jpg"]


def test_saveStage_runsAfterAnalyze_onlyWhenRegistered(tmp_path: Path) -> None:
    inputDir, outputDir = tree_make(tmp_path)
    tool: Tool = Tool(fileFilter="glob:*.jpg", verbosity=0)
    order: list[str] = []

    @tool.analyze
    def stage_one(node: DirNode, read: StageResult) -> StageResult:
        order.append("analyze:" + node.relPath)
        return StageResult(status=True, files=read.files, payload={"count": len(read.files)})

    @tool.save
    def stage_two(node: DirNode, analyzed: StageResult) -> StageResult:
        order.append("save:" + node.relPath)
        (node.outputPath / "count").write_text(str(analyzed.payload["count"]))
        return StageResult(status=True, files=["count"])

    assert tool(inputDir, outputDir).status is True
    assert order.index("analyze:a") < order.index("save:a")
    assert (outputDir / "a" / "count").read_text() == "2"
    assert stage_one is not tool and callable(stage_one)


def test_readStage_registered(tmp_path: Path) -> None:
    inputDir, outputDir = tree_make(tmp_path)
    tool: Tool = Tool(verbosity=0, relativeDir=True)

    @tool.read
    def only_txt(node: DirNode) -> StageResult:
        files: list[str] = [name for name in node.files if name.endswith(".txt")]
        return StageResult(status=bool(files), files=files)

    @tool.analyze
    def keep(node: DirNode, read: StageResult) -> StageResult:
        return StageResult(status=True, files=read.files)

    result: RunResult = tool(inputDir, outputDir)
    assert result.process is not None
    assert result.process.read["a"].status is True and result.process.read["b/c"].status is False
    assert result.process.read["a"].files == ["note.txt"]


def test_failingStage_dropsDirectory_runContinues(tmp_path: Path) -> None:
    inputDir, outputDir = tree_make(tmp_path)

    @analyze(fileFilter="glob:*.jpg", verbosity=0, relativeDir=True)
    def flaky(node: DirNode, read: StageResult) -> StageResult:
        if node.relPath == "a":
            raise RuntimeError("a is bad")
        return StageResult(status=True, files=read.files)

    result: RunResult = flaky(inputDir, outputDir)
    assert result.status is True and result.process is not None
    assert result.process.analyze["a"].status is False and result.process.analyze["b/c"].status is True
    assert result.process.dirsProcessed == 1


def test_commandForm_parsesFlags_defaultsFromDecorator(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    inputDir, outputDir = tree_make(tmp_path)
    seen: list[str] = []

    @analyze(fileFilter="glob:*.jpg", analyzeFileIndex="f")
    def cmd(node: DirNode, read: StageResult) -> StageResult:
        seen.extend(read.files)
        return StageResult(status=True, files=read.files)

    dirs: list[str] = ["--inputDir", str(inputDir), "--outputDir", str(outputDir), "--verbosity", "0"]
    assert cmd.main([*dirs, "--json"]) == 0
    assert sorted(seen) == ["one.jpg", "three.jpg"]
    assert json.loads(capsys.readouterr().out)["status"] is True
    seen.clear()
    assert cmd.main([*dirs, "--analyzeFileIndex", "a"]) == 0
    assert sorted(seen) == ["one.jpg", "three.jpg", "two.jpg"]


def test_commandForm_helpAndVersion_nameTheTool(capsys: pytest.CaptureFixture[str]) -> None:
    tool: Tool = analyze()(copy_toPng)
    with pytest.raises(SystemExit):
        tool.main(["--version"])
    assert capsys.readouterr().out.startswith("copy_toPng ")
    with pytest.raises(SystemExit):
        tool.main(["--help"])
    assert "copy_toPng --man" in capsys.readouterr().out
    assert tool.main(["--synopsis"]) == 0


def test_commandForm_exitStatus(tmp_path: Path) -> None:
    inputDir, outputDir = tree_make(tmp_path)

    @analyze(fileFilter="glob:*.jpg", verbosity=0)
    def failing(node: DirNode, read: StageResult) -> StageResult:
        return StageResult(status=False, files=[])

    assert failing.main(["--inputDir", str(inputDir), "--outputDir", str(outputDir)]) == 1
    with pytest.raises(SystemExit) as exit_:
        failing.main(["--outputDir", str(outputDir)])
    assert exit_.value.code == 2


def test_pluginForm_parsedNamespace_andDecoratorDefaults(tmp_path: Path) -> None:
    inputDir, outputDir = tree_make(tmp_path)
    seen: list[str] = []

    @analyze(fileFilter="glob:*.jpg", analyzeFileIndex="f", verbosity=0)
    def plugin_main(node: DirNode, read: StageResult) -> StageResult:
        seen.extend(read.files)
        return StageResult(status=True, files=read.files)

    parser: argparse.ArgumentParser = plugin_main.parser(standalone=False)
    assert all(action.option_strings for action in parser._actions)
    options: argparse.Namespace = parser.parse_args([])
    assert plugin_main(options, inputDir, outputDir) == 0
    assert sorted(seen) == ["one.jpg", "three.jpg"]
    seen.clear()
    plain: argparse.Namespace = plugin_main.parser(standalone=False).parse_args(["--analyzeFileIndex", "a"])
    assert plugin_main.plugin(plain, inputDir, outputDir) == 0
    assert sorted(seen) == ["one.jpg", "three.jpg", "two.jpg"]


def test_pluginForm_underChrisPlugin(tmp_path: Path) -> None:
    chris_plugin = pytest.importorskip("chris_plugin")
    inputDir, outputDir = tree_make(tmp_path)
    tool: Tool = analyze(fileFilter="glob:*.jpg", verbosity=0)(copy_toPng)
    decorate = chris_plugin.chris_plugin(
        parser=tool.parser(standalone=False), title="JPG to PNG", singleton=False
    )
    main = decorate(tool)
    options: argparse.Namespace = tool.parser(standalone=False).parse_args([])
    assert main(options, inputDir, outputDir) == 0
    assert (outputDir / "b" / "c" / "three.png").exists()


def test_call_withWrongArity_raises() -> None:
    tool: Tool = analyze()(copy_toPng)
    with pytest.raises(TypeError):
        tool("only-one")
