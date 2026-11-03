"""pfdo: walk a tree with pftree and do something in every directory.

``Pfdo`` is the base class of a family of tools (pfdo_run, pfdo_med2image and
others) that each do one thing per directory of an input tree and write their
results to the same place in an output tree. It is a ``Pftree`` whose three
callbacks are meant to be overridden, plus one convenience the family shares: the
``--analyzeFileIndex`` choice of which of a directory's files the analyze step gets.

A subclass overrides the callbacks it needs and nothing else. The base class's own
callbacks pass through: read lists the files, analyze selects by index, save touches
nothing. When the index leaves out a volume of a directory, a file ``v`` would have
run on its own, a warning names it, so a dropped scan is never silent. Only the
stages a subclass overrides run, and overriding any of them is enough for ``run()``
to process the tree. ``pfdo --test`` runs the demonstration
callbacks instead, which prefix each selected name with ``analyzed-`` and touch those
names in the output directory.

Key components:
    - Pfdo: the base class; override ``inputAnalyze_callback`` and/or
      ``outputSave_callback``
    - fileIndex_select: the ``--analyzeFileIndex`` rule, as a pure function
    - volumes_select, volumes_dropped: the volume rule behind ``v`` and the warning
    - volume_name: what a volume is called, for the tools that name outputs after it

Typical usage:
    from pfdo.models import DirNode, PfdoOptions, StageResult

    class Mine(Pfdo):
        def inputAnalyze_callback(self, node: DirNode, read: StageResult) -> StageResult:
            for name in self.filesToAnalyze(node):
                ...

    Mine(PfdoOptions.fromDict(vars(args))).run()

Dependencies:
    - pftree
"""

from __future__ import annotations

import logging
from pathlib import Path, PurePath

from pftree.tree import Pftree

from pfdo.models import (
    FILE_INDEX_ALL,
    FILE_INDEX_FIRST,
    FILE_INDEX_LAST,
    FILE_INDEX_MIDDLE,
    FILE_INDEX_VOLUME,
    DirNode,
    PfdoOptions,
    ProcessResult,
    RunResult,
    StageResult,
)

logger: logging.Logger = logging.getLogger("pfdo")

ANALYZED_PREFIX: str = "analyzed-"
CALLBACK_NAMES: tuple[str, str, str] = ("inputRead_callback", "inputAnalyze_callback", "outputSave_callback")
DICOM_SUFFIX: str = ".dcm"
COMPRESSION_SUFFIXES: tuple[str, ...] = (".gz", ".bz2", ".xz", ".zst")


def file_isDicom(name: str) -> bool:
    """Whether a file name ends in ``.dcm``, in any case."""
    return name.lower().endswith(DICOM_SUFFIX)


def volume_key(name: str) -> str:
    """The volume a file belongs to: every ``.dcm`` shares one, any other file is its own."""
    return DICOM_SUFFIX if file_isDicom(name) else name


def volumes_select(files: list[str]) -> list[str]:
    """One file per volume of a directory.

    The ``.dcm`` files together are one volume, a series, given by its first name in
    sorted order; every other file is a volume of its own. Which files are there at
    all is the ``--fileFilter``'s choice, so a tool keeps sidecars out by its filter.

    Args:
        files: the directory's file names, in order.

    Returns:
        The first ``.dcm`` and every other file, in their original order.

    Example:
        >>> volumes_select(["a.nii.gz", "s02.dcm", "s01.dcm", "b.nii.gz"])
        ['a.nii.gz', 's01.dcm', 'b.nii.gz']
    """
    dicoms: list[str] = [name for name in files if file_isDicom(name)]
    series: str | None = min(dicoms) if dicoms else None
    return [name for name in files if not file_isDicom(name) or name == series]


def volume_name(dirName: str, fileName: str, files: list[str]) -> str:
    """The name of the volume a selected file stands for.

    A volume alone in its directory, and a DICOM series anywhere, is named after the
    directory, so ``sub-01/t1.nii.gz`` is ``sub-01``. A file sharing its directory
    with other volumes is named after its own name less its extension, and less a
    compression suffix before that, so ``scan01.nii.gz`` beside ``scan02.nii.gz`` is
    ``scan01`` and ``meeting.mp4`` beside another recording is ``meeting``.

    Args:
        dirName: the name of the file's directory.
        fileName: the file.
        files: the directory's files, after the filters, which say how many volumes
            it holds.

    Returns:
        The volume's name.

    Example:
        >>> volume_name("sub-01", "t1.nii.gz", ["t1.nii.gz"])
        'sub-01'
        >>> volume_name("sub-02", "scan.v2.nii.gz", ["scan.v2.nii.gz", "scan.v3.nii.gz"])
        'scan.v2'
        >>> volume_name("T1_MPRAGE", "im001.dcm", ["im001.dcm", "im002.dcm", "t1.nii"])
        'T1_MPRAGE'
    """
    if file_isDicom(fileName) or len(volumes_select(files)) <= 1:
        return dirName
    path: PurePath = PurePath(fileName)
    if path.suffix.lower() in COMPRESSION_SUFFIXES:
        path = path.with_suffix("")
    return path.stem


def volumes_dropped(files: list[str], selected: list[str]) -> list[str]:
    """The volumes of a directory that a selection leaves out.

    A volume is kept when any of its files is selected: a DICOM series by any of its
    slices, so ``f`` on a series directory drops nothing.

    Args:
        files: the directory's file names.
        selected: the files an index chose from them.

    Returns:
        One name per volume left out, as ``volumes_select`` gives it.

    Example:
        >>> volumes_dropped(["s1.dcm", "s2.dcm", "t1.nii"], ["s1.dcm"])
        ['t1.nii']
    """
    kept: set[str] = {volume_key(name) for name in selected}
    return [name for name in volumes_select(files) if volume_key(name) not in kept]


def fileIndex_select(files: list[str], spec: str) -> list[str]:
    """Pick the files ``--analyzeFileIndex`` names out of a directory's list.

    Args:
        files: the directory's file names, in order.
        spec: ``a`` for all, ``f`` first, ``l`` last, ``m`` middle, ``v`` one per
            volume (see ``volumes_select``), or an integer. An integer wraps: ``-1``
            is the last file, ``len(files)`` the first again.

    Returns:
        The chosen files, in their original order; empty when ``files`` is empty.

    Raises:
        ValueError: if ``spec`` is none of the above.

    Example:
        >>> fileIndex_select(["a", "b", "c"], "m")
        ['b']
        >>> fileIndex_select(["a", "b", "c"], "-1")
        ['c']
    """
    if not files:
        return []
    match spec:
        case s if s == FILE_INDEX_ALL:
            return list(files)
        case s if s == FILE_INDEX_FIRST:
            return [files[0]]
        case s if s == FILE_INDEX_LAST:
            return [files[-1]]
        case s if s == FILE_INDEX_MIDDLE:
            return [files[len(files) // 2]]
        case s if s == FILE_INDEX_VOLUME:
            return volumes_select(files)
        case _:
            try:
                index: int = int(spec)
            except ValueError as err:
                raise ValueError(
                    f"analyzeFileIndex must be a, f, l, m, v or an integer, not {spec!r}"
                ) from err
            return [files[index % len(files)]]


class Pfdo(Pftree):
    """Walk an input tree and run a per-directory read / analyze / save sequence.

    Attributes:
        options: the PfdoOptions in force.
        processAlways: a subclass may set this True to process even when it overrides
            no callback; overriding one is enough on its own.

    Example:
        >>> tool = Pfdo(PfdoOptions(inputDir=Path("."), outputDir=Path("/tmp/out"), verbosity=0))
        >>> tool.run().status
        True
    """

    processAlways: bool = False

    def __init__(self, options: PfdoOptions) -> None:
        super().__init__(options)
        self.options: PfdoOptions = options

    def filesToAnalyze(self, node: DirNode) -> list[str]:
        """The files of a directory that ``--analyzeFileIndex`` selects.

        Args:
            node: the directory.

        Returns:
            The selected names, in order.
        """
        return self.files_select(node, node.files)

    def files_select(self, node: DirNode, files: list[str]) -> list[str]:
        """Apply ``--analyzeFileIndex`` to a directory's files, warning of dropped volumes.

        Args:
            node: the directory, for the warning.
            files: its files.

        Returns:
            The selected names, in order.
        """
        spec: str = self.options.analyzeFileIndex
        selected: list[str] = fileIndex_select(files, spec)
        dropped: list[str] = volumes_dropped(files, selected)
        if dropped:
            logger.warning(
                "%s: --analyzeFileIndex %s leaves out %d more volume(s): %s; --analyzeFileIndex v runs each",
                node.relPath,
                spec,
                len(dropped),
                ", ".join(dropped),
            )
        return selected

    def callback_isOverridden(self, name: str) -> bool:
        """Whether a subclass defines the named callback.

        Args:
            name: one of ``CALLBACK_NAMES``.

        Returns:
            True when the method on this class is not ``Pfdo``'s own.
        """
        return getattr(type(self), name) is not getattr(Pfdo, name)

    def inputRead_callback(self, node: DirNode) -> StageResult:
        """Default read: list the directory's files without opening them.

        Args:
            node: the directory.

        Returns:
            Success with the files; failure if there are none.
        """
        logger.debug("reading %s: %d files", node.relPath, len(node.files))
        return StageResult(status=bool(node.files), files=list(node.files))

    def inputAnalyze_callback(self, node: DirNode, read: StageResult) -> StageResult:
        """Default analyze: pass the selected files through, untouched.

        Args:
            node: the directory.
            read: the read stage's result.

        Returns:
            Success with the files ``--analyzeFileIndex`` selects; failure when it
            selects nothing.
        """
        selected: list[str] = self.files_select(node, read.files)
        logger.debug("analyzing %s: %s", node.relPath, selected)
        return StageResult(status=bool(selected), files=selected)

    def outputSave_callback(self, node: DirNode, analyze: StageResult) -> StageResult:
        """Default save: write nothing.

        Args:
            node: the directory.
            analyze: the analyze stage's result.

        Returns:
            Success with no files.
        """
        return StageResult(status=True, files=[])

    def demoAnalyze_callback(self, node: DirNode, read: StageResult) -> StageResult:
        """Demonstration analyze, run by ``--test``: select by index and tag each name.

        Args:
            node: the directory.
            read: the read stage's result.

        Returns:
            Success with ``analyzed-<name>`` for every selected file; failure when
            the index selects nothing.
        """
        selected: list[str] = self.files_select(node, read.files)
        logger.debug("analyzing %s: %s", node.relPath, selected)
        return StageResult(status=bool(selected), files=[ANALYZED_PREFIX + name for name in selected])

    def demoSave_callback(self, node: DirNode, analyze: StageResult) -> StageResult:
        """Demonstration save, run by ``--test``: touch each analyzed name in the output directory.

        Args:
            node: the directory; its ``outputPath`` is created.
            analyze: the analyze stage's result.

        Returns:
            Success with the names written. An existing file stops the directory
            with a failure unless ``overwrite`` is set.
        """
        node.outputPath.mkdir(parents=True, exist_ok=True)
        saved: list[str] = []
        for name in analyze.files:
            target: Path = node.outputPath / name
            if target.exists() and not self.options.overwrite:
                logger.error("%s exists; run with --overwrite to replace it", target)
                return StageResult(status=False, files=saved)
            target.touch()
            saved.append(name)
        logger.debug("saved %d files in %s", len(saved), node.outputPath)
        return StageResult(status=True, files=saved)

    def callbacks_run(self) -> ProcessResult:
        """Run the stages over the tree.

        Under ``--test`` the three demonstration callbacks run. Otherwise read always
        runs, and analyze and save run only when the subclass overrides them, so a
        tool that only analyzes never has a save stage touching its output tree.
        """
        if self.options.testRun and not self.processAlways:
            return self.tree_process(
                inputRead_callback=self.inputRead_callback,
                inputAnalyze_callback=self.demoAnalyze_callback,
                outputWrite_callback=self.demoSave_callback,
            )
        return self.tree_process(
            inputRead_callback=self.inputRead_callback,
            inputAnalyze_callback=(
                self.inputAnalyze_callback if self.callback_isOverridden("inputAnalyze_callback") else None
            ),
            outputWrite_callback=(
                self.outputSave_callback if self.callback_isOverridden("outputSave_callback") else None
            ),
        )

    def shouldProcess(self) -> bool:
        """Whether ``run`` processes the tree after probing and filtering it."""
        return (
            self.processAlways
            or self.options.testRun
            or any(self.callback_isOverridden(name) for name in CALLBACK_NAMES)
        )

    def run(self) -> RunResult:
        """Probe, filter, then process when a callback is overridden or ``--test`` asks.

        Returns:
            The run's result; ``status`` is False with ``error`` set when the input
            directory is missing, or when processing failed in every directory.
        """
        error: str = self.env_check()
        if error:
            logger.error(error)
            return RunResult(status=False, error=error, runTime=self.runTime_get())
        self.tree_construct(self.tree_probe())
        if self.fileTokens or self.dirTokens:
            self.tree_filter()
        process: ProcessResult | None = None
        status: bool = True
        if self.shouldProcess():
            process = self.callbacks_run()
            status = process.status
        return RunResult(status=status, tree=dict(self.tree), process=process, runTime=self.runTime_get())
