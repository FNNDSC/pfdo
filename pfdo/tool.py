"""Attaching a task to the frame by decorator instead of by subclass.

A ``Tool`` is the frame around a per-directory task: pfdo's options, selection, run,
report and command line, with the stages supplied as plain functions rather than as
methods of a subclass. ``@tool.read``, ``@tool.analyze`` and ``@tool.save`` register a
function for a stage; ``analyze(...)`` is the one-stage shorthand that turns the
decorated function into a ``Tool``. Underneath, a ``Pfdo`` subclass is built on the fly
whose callbacks call the registered functions, so a decorated tool runs through the
same engine, honours the same flags and returns the same record as a subclass.

A ``Tool`` is called three ways. With an input and an output directory it runs and
returns the ``RunResult``. With nothing it is a command: pfdo's parser is parsed from
the command line, with the decorator's keywords as the flags' defaults, and the exit
status comes back. With a parsed ``Namespace`` and two directories it is a ChRIS
plugin's main, which is what ``@chris_plugin`` calls; the tool carries the signature
``@chris_plugin`` inspects, so it can sit directly under that decorator.

Key components:
    - Tool: the frame, with stages attached by decorator
    - analyze: one-stage shorthand
    - ReadStage, Stage: the stage function types

Typical usage:
    @analyze(fileFilter="glob:*.jpg", threads=4)
    def jpgs_toPng(node: DirNode, read: StageResult) -> StageResult:
        for name in read.files:
            convert(node.path / name, node.outputPath / Path(name).with_suffix(".png"))
        return StageResult(status=True, files=read.files)

    jpgs_toPng(inputDir, outputDir)       # from Python
    sys.exit(jpgs_toPng())                # from a shell, pfdo's flags

Dependencies:
    - pfdo.pfdo, pfdo.models, pfdo.__main__ (lazily, for the command form)
"""

from __future__ import annotations

import argparse
import inspect
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pfdo.models import DirNode, PfdoOptions, RunResult, StageResult
from pfdo.pfdo import Pfdo

logger: logging.Logger = logging.getLogger("pfdo")

ReadStage = Callable[[DirNode], StageResult]
Stage = Callable[[DirNode, StageResult], StageResult]

STAGE_NAMES: tuple[str, str, str] = ("read", "analyze", "save")
EXIT_OK: int = 0
EXIT_FAILED: int = 1

PLUGIN_SIGNATURE: inspect.Signature = inspect.Signature(
    [
        inspect.Parameter("options", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=argparse.Namespace),
        inspect.Parameter("inputdir", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Path),
        inspect.Parameter("outputdir", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Path),
    ],
    return_annotation=int,
)


class Tool:
    """The frame around a per-directory task, with its stages attached by decorator.

    Attributes:
        defaults: the option values the decorator was given; the flags' defaults in
            the command and plugin forms, the baseline under ``run``'s overrides.
        stages: the registered stage functions, by stage name.
        name: the tool's name, for the command's ``--help`` and ``--version``.

    Example:
        >>> tool = Tool(fileFilter="glob:*.jpg")
        >>> @tool.analyze
        ... def convert_all(node: DirNode, read: StageResult) -> StageResult:
        ...     return StageResult(status=True, files=read.files)
        >>> sorted(tool.stages)
        ['analyze']
    """

    def __init__(self, name: str = "pfdo", **defaults: object) -> None:
        self.name: str = name
        self.defaults: dict[str, object] = dict(defaults)
        self.stages: dict[str, Callable[..., StageResult]] = {}
        self.__name__: str = name
        self.__qualname__: str = name
        self.__doc__: str | None = None
        self.__signature__: inspect.Signature = PLUGIN_SIGNATURE

    def read(self, func: ReadStage) -> ReadStage:
        """Register the read stage: ``(node) -> StageResult``."""
        self.stages["read"] = func
        return func

    def analyze(self, func: Stage) -> Stage:
        """Register the analyze stage: ``(node, read) -> StageResult``.

        The ``read`` result the function receives lists the files ``--analyzeFileIndex``
        selects, and the directory's ``outputPath`` exists.
        """
        self.stages["analyze"] = func
        return func

    def save(self, func: Stage) -> Stage:
        """Register the save stage: ``(node, analyzed) -> StageResult``."""
        self.stages["save"] = func
        return func

    def engine_build(self, options: PfdoOptions) -> Pfdo:
        """A ``Pfdo`` subclass whose callbacks call the registered stages, instantiated.

        Only the registered stages exist on the subclass, so pfdo's rule that only
        overridden stages run applies unchanged.
        """
        stages: dict[str, Callable[..., StageResult]] = self.stages
        attrs: dict[str, object] = {"__doc__": f"The engine of the tool {self.name}."}
        if "read" in stages:

            def inputRead_callback(self_: Pfdo, node: DirNode) -> StageResult:
                return stages["read"](node)

            attrs["inputRead_callback"] = inputRead_callback
        if "analyze" in stages:

            def inputAnalyze_callback(self_: Pfdo, node: DirNode, read: StageResult) -> StageResult:
                node.outputPath.mkdir(parents=True, exist_ok=True)
                chosen: list[str] = self_.filesToAnalyze(node)
                selected: StageResult = StageResult(status=bool(chosen), files=chosen, payload=read.payload)
                return stages["analyze"](node, selected)

            attrs["inputAnalyze_callback"] = inputAnalyze_callback
        if "save" in stages:

            def outputSave_callback(self_: Pfdo, node: DirNode, analyze: StageResult) -> StageResult:
                return stages["save"](node, analyze)

            attrs["outputSave_callback"] = outputSave_callback
        engineClass: type[Pfdo] = type(f"{self.name}Engine", (Pfdo,), attrs)
        return engineClass(options)

    def options_build(self, inputDir: Path | str, outputDir: Path | str, **overrides: object) -> PfdoOptions:
        """The options for one run: the defaults, then the overrides, then the directories."""
        values: dict[str, object] = {**self.defaults, **overrides}
        values.update(inputDir=inputDir, outputDir=outputDir)
        return PfdoOptions.fromDict(values)

    def run(self, inputDir: Path | str, outputDir: Path | str, **overrides: object) -> RunResult:
        """Run the tool over a tree.

        Args:
            inputDir: the input tree.
            outputDir: the output tree.
            **overrides: option values for this run, over the decorator's defaults.

        Returns:
            The run's record.
        """
        return self.engine_build(self.options_build(inputDir, outputDir, **overrides)).run()

    def parser(self, standalone: bool = True) -> argparse.ArgumentParser:
        """pfdo's parser with this tool's name and the decorator's keywords as the flags' defaults.

        Args:
            standalone: include ``--inputDir`` / ``--outputDir``; a ChRIS plugin passes
                False and lets ``@chris_plugin`` add its positional directories.
        """
        from pfdo import __version__
        from pfdo.__main__ import parser_build

        built: argparse.ArgumentParser = parser_build(
            standalone=standalone, command=self.name, version=__version__
        )
        built.set_defaults(**self.defaults)
        return built

    def options_fromNamespace(self, options: argparse.Namespace) -> PfdoOptions:
        """Options from a parsed namespace, the decorator's defaults beneath it.

        A parser built by ``parser()`` already carries the decorator's keywords as its
        flags' defaults, so what the command line did not say arrives as those; a
        parser built elsewhere yields them only for flags it does not define.
        """
        values: dict[str, object] = {**self.defaults, **vars(options)}
        return PfdoOptions.fromDict(values)

    def plugin(self, options: argparse.Namespace, inputdir: Path | str, outputdir: Path | str) -> int:
        """The tool as a ChRIS plugin's main: what ``@chris_plugin`` calls.

        Args:
            options: the flags ``@chris_plugin`` parsed.
            inputdir: the positional input directory.
            outputdir: the positional output directory.

        Returns:
            0 when the run succeeded, 1 otherwise.
        """
        from pftree.__main__ import logging_configure

        from pfdo.__main__ import result_report

        built: PfdoOptions = self.options_fromNamespace(options)
        built.inputDir = Path(inputdir)
        built.outputDir = Path(outputdir)
        logging_configure(built.verbosity)
        result: RunResult = self.engine_build(built).run()
        result_report(options, result)
        if result.error:
            print(result.error, file=sys.stderr)
        return EXIT_OK if result.status else EXIT_FAILED

    def main(self, argv: list[str] | None = None) -> int:
        """The tool as a command: pfdo's flags, this tool's name.

        Args:
            argv: arguments without the program name; ``None`` reads ``sys.argv``.

        Returns:
            The exit status: 0 on success, 1 when the run failed, 2 on bad arguments.
        """
        from pftree.__main__ import logging_configure
        from pftree.manual import manual_print

        from pfdo.__main__ import manual_build, result_report

        parser: argparse.ArgumentParser = self.parser()
        args: argparse.Namespace = parser.parse_args(argv)
        if args.man or args.synopsis:
            manual_print(manual_build(), shortOnly=not args.man)
            return EXIT_OK
        if not args.inputDir:
            parser.error("--inputDir is required")
        try:
            options: PfdoOptions = self.options_fromNamespace(args)
        except ValueError as err:
            parser.error(str(err))
        logging_configure(options.verbosity)
        result: RunResult = self.engine_build(options).run()
        result_report(args, result)
        if result.error:
            print(result.error, file=sys.stderr)
        return EXIT_OK if result.status else EXIT_FAILED

    def __call__(self, *args: Any, **overrides: object) -> Any:
        """Run, as a command, from Python, or as a plugin, by how it is called.

        No arguments: the command, returning the exit status. Two: input and output
        directories, returning the ``RunResult``. Three: a ``Namespace`` and the two
        directories, the plugin form, returning the exit status.
        """
        if not args:
            return self.main()
        if len(args) == 2:
            return self.run(args[0], args[1], **overrides)
        if len(args) == 3 and isinstance(args[0], argparse.Namespace):
            return self.plugin(args[0], args[1], args[2])
        raise TypeError(
            f"{self.name}: call with no arguments, two directories, or (options, inputdir, outputdir)"
        )


def analyze(**defaults: object) -> Callable[[Stage], Tool]:
    """Make a one-stage tool from an analyze function.

    Args:
        **defaults: pfdo option values, as ``fileFilter="glob:*.jpg"`` or ``threads=4``.

    Returns:
        A decorator that returns the ``Tool``, named after the function.

    Example:
        >>> @analyze(fileFilter="txt")
        ... def count(node: DirNode, read: StageResult) -> StageResult:
        ...     return StageResult(status=True, files=read.files)
        >>> count.name, sorted(count.stages)
        ('count', ['analyze'])
    """

    def decorator(func: Stage) -> Tool:
        tool: Tool = Tool(name=func.__name__, **defaults)
        tool.analyze(func)
        tool.__doc__ = func.__doc__
        tool.__module__ = func.__module__
        return tool

    return decorator
