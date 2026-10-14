"""The data models of pfdo.

pfdo adds two options to pftree's: which file(s) in each directory the analyze
callback should work on, and whether the base class's demonstration callbacks run.
Everything else, from the input and output directories to the filters and threads,
is pftree's ``TreeOptions``.

Key components:
    - PfdoOptions: ``TreeOptions`` plus ``analyzeFileIndex`` and ``testRun``
    - fileIndex_validate: the grammar of ``--analyzeFileIndex``
    - DirNode, StageResult, ProcessResult, RunResult, TreeOptions: pftree's models,
      re-exported so a tool built on pfdo imports from pfdo alone

Typical usage:
    options = PfdoOptions.fromDict(vars(args))
    Pfdo(options).run()

Dependencies:
    - pftree.models
"""

from __future__ import annotations

from dataclasses import dataclass

from pftree.models import DirNode, ProcessResult, RunResult, StageResult, TreeOptions

FILE_INDEX_ALL: str = "a"
FILE_INDEX_FIRST: str = "f"
FILE_INDEX_LAST: str = "l"
FILE_INDEX_MIDDLE: str = "m"
FILE_INDEX_WORDS: tuple[str, ...] = (FILE_INDEX_ALL, FILE_INDEX_FIRST, FILE_INDEX_LAST, FILE_INDEX_MIDDLE)


def fileIndex_validate(spec: str) -> None:
    """Check an ``--analyzeFileIndex`` value.

    Args:
        spec: ``a``, ``f``, ``l``, ``m`` or an integer, possibly negative.

    Raises:
        ValueError: for anything else.
    """
    if spec in FILE_INDEX_WORDS:
        return
    try:
        int(spec)
    except ValueError as err:
        raise ValueError(f"analyzeFileIndex must be a, f, l, m or an integer, not {spec!r}") from err


@dataclass
class PfdoOptions(TreeOptions):
    """pftree's options plus pfdo's own.

    Attributes:
        analyzeFileIndex: which of a directory's files the analyze callback gets:
            ``a`` all (the default), ``f`` the first, ``l`` the last, ``m`` the
            middle, or an integer index that wraps in either direction.
        testRun: run the base class's demonstration callbacks over the tree.

    Example:
        >>> PfdoOptions.fromDict({"inputDir": "/in", "analyzeFileIndex": "-1"}).analyzeFileIndex
        '-1'
    """

    analyzeFileIndex: str = FILE_INDEX_ALL
    testRun: bool = False

    def __post_init__(self) -> None:
        """Validate pftree's options and then ``analyzeFileIndex``.

        Raises:
            ValueError: on a bad filter, leaf template or file index.
        """
        super().__post_init__()
        fileIndex_validate(self.analyzeFileIndex)


__all__: list[str] = [
    "FILE_INDEX_ALL",
    "FILE_INDEX_FIRST",
    "FILE_INDEX_LAST",
    "FILE_INDEX_MIDDLE",
    "FILE_INDEX_WORDS",
    "DirNode",
    "PfdoOptions",
    "ProcessResult",
    "RunResult",
    "StageResult",
    "TreeOptions",
    "fileIndex_validate",
]
