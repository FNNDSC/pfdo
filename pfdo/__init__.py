"""pfdo: walk a directory tree with pftree and do something in every directory.

The base class of a family of tools, each doing one thing per directory of an input
tree and writing results to the same place in an output tree. ``Pfdo`` is a
``Pftree`` whose callbacks are meant to be overridden, plus the family's shared
``--analyzeFileIndex`` choice of which files the analyze step gets.

Key components:
    - Pfdo: the base class, for a task attached by subclass
    - Tool, analyze: the frame with a task attached by decorator
    - PfdoOptions: pftree's options plus pfdo's
    - fileIndex_select: the ``--analyzeFileIndex`` rule
    - __main__: the ``pfdo`` command line, its manual, and the parts a package
      built on pfdo assembles its own from

Typical usage:
    from pfdo import Pfdo, PfdoOptions
    Pfdo(PfdoOptions(inputDir=Path("/in"), outputDir=Path("/out"), testRun=True)).run()

    from pfdo import analyze
    @analyze(fileFilter="glob:*.jpg")
    def convert_all(node, read): ...
    convert_all("/in", "/out")

Dependencies:
    - pftree
"""

from __future__ import annotations

__version__: str = "6.2.1"

from pfdo.models import DirNode, PfdoOptions, ProcessResult, RunResult, StageResult, fileIndex_validate
from pfdo.pfdo import ANALYZED_PREFIX, Pfdo, fileIndex_select
from pfdo.tool import Tool, analyze

__all__ = [
    "ANALYZED_PREFIX",
    "DirNode",
    "Pfdo",
    "PfdoOptions",
    "ProcessResult",
    "RunResult",
    "StageResult",
    "Tool",
    "__version__",
    "analyze",
    "fileIndex_select",
    "fileIndex_validate",
]
