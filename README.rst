pfdo
====

.. image:: https://github.com/FNNDSC/pfdo/actions/workflows/ci.yml/badge.svg
    :target: https://github.com/FNNDSC/pfdo/actions/workflows/ci.yml

.. image:: https://img.shields.io/pypi/v/pfdo.svg
    :target: https://pypi.org/project/pfdo/

.. image:: https://img.shields.io/badge/python-3.11%2B-blue.svg
    :target: https://pypi.org/project/pfdo/

Walk a directory tree with ``pftree`` and do something in every directory: the base class of the pfdo family.

.. contents:: Table of Contents

Overview
--------

``pfdo`` is the base class of a family of tools (``pfdo_run``, ``pfdo_med2image``, ``pfdo_mgz2image`` and others) that each do one thing per directory of an input tree and write their results to the same place in an output tree. It is a ``pftree.Pftree`` whose three callbacks, read, analyze and save, are meant to be overridden, plus one convenience the family shares: ``--analyzeFileIndex``, the choice of which of a directory's files the analyze step gets. A subclass overrides the callbacks it needs and nothing else: only overridden stages run, and overriding one is enough for ``run()`` to process the tree.

On its own, ``pfdo`` walks a tree, applies ``pftree``'s filters, and with ``--test`` runs its demonstration callbacks: read lists each directory's files, analyze selects by index and prefixes every name with ``analyzed-``, save touches those names in the output directory. Without ``--test`` the base class touches nothing.

Installation
------------

.. code:: bash

    pip install pfdo

Python 3.11 or newer; depends on ``pftree``.

Command line
------------

.. code:: bash

    pfdo --inputDir /data --outputDir /tmp/out --fileFilter jpg --test --json
    pfdo --inputDir /data --outputDir /tmp/out --dirFilter 100307 --analyzeFileIndex m --test
    pfdo --man

``pfdo --man`` prints the full manual, ``--synopsis`` its first page, ``--help`` the quick reference. All of ``pftree``'s options apply (``--fileFilter``, ``--dirFilter`` and their logic, ``--maxDepth``, ``--outputLeafDir``, ``--threads``, ``--relativeDir``, ``--followLinks``, ``--overwrite``, ``--json``, ``--printElapsedTime``); ``pfdo`` adds:

``--analyzeFileIndex <a|f|l|m|N>``
    Which of a directory's files the analyze step receives: ``a`` all (default), ``f`` first, ``l`` last, ``m`` middle, or an integer index that wraps in either direction (``-1`` is the last file, ``len`` the first again).

``--test``
    Run the demonstration callbacks. An output file that already exists stops that directory unless ``--overwrite`` is given.

Library
-------

.. code:: python

    from pathlib import Path
    from pfdo import Pfdo
    from pfdo.models import DirNode, PfdoOptions, StageResult

    class Counter(Pfdo):
        def inputAnalyze_callback(self, node: DirNode, read: StageResult) -> StageResult:
            chosen = self.filesToAnalyze(node)
            return StageResult(status=True, files=chosen, payload={"count": len(chosen)})

        def outputSave_callback(self, node: DirNode, analyze: StageResult) -> StageResult:
            node.outputPath.mkdir(parents=True, exist_ok=True)
            (node.outputPath / "count.txt").write_text(f"{analyze.payload['count']}\n")
            return StageResult(status=True, files=["count.txt"])

    result = Counter(PfdoOptions(inputDir=Path("/data"), outputDir=Path("/out"), threads=4)).run()

``PfdoOptions`` is ``pftree.TreeOptions`` plus ``analyzeFileIndex`` and ``testRun``; ``PfdoOptions.fromDict(vars(args))`` builds it from an argparse ``Namespace`` and ignores keys it does not know. ``pfdo.models`` re-exports ``DirNode``, ``StageResult``, ``ProcessResult`` and ``RunResult`` from ``pftree``, so a tool built on pfdo imports from pfdo alone. A subclass overrides ``inputAnalyze_callback``, ``outputSave_callback`` or both; it calls ``self.filesToAnalyze(node)`` to honour ``--analyzeFileIndex``. ``run()`` returns ``RunResult`` (``status``, ``tree``, ``process``, ``runTime``).

For its command line, a package built on pfdo composes ``pfdo.__main__``'s parts: ``parserSelf_build()`` and ``pftree``'s ``parserCore_build()`` / ``parserIO_build()`` for the parser, ``synopsis(command=...)`` or the ``CLI_*`` and ``ARGS_SYNOPSIS_*`` texts for the manual, and ``pftree.manual.Manual`` with ``manual_print`` to render it.

The decorator
-------------

A task that is one stage, and does not override the engine, can be a function instead of a subclass. ``analyze`` turns it into a ``Tool``: the same frame, the same flags, the same record.

.. code:: python

    from pathlib import Path
    from pfdo import analyze
    from pfdo.models import DirNode, StageResult

    @analyze(fileFilter="glob:*.jpg", threads=4)
    def jpgs_toPng(node: DirNode, read: StageResult) -> StageResult:
        for name in read.files:
            convert(node.path / name, node.outputPath / Path(name).with_suffix(".png"))
        return StageResult(status=True, files=read.files)

``read.files`` arrives already selected by ``--analyzeFileIndex`` and ``node.outputPath`` already exists. The decorated name is callable three ways:

.. code:: python

    result = jpgs_toPng("/data", "/out")          # from Python: a RunResult
    sys.exit(jpgs_toPng())                        # from a shell: pfdo's flags, the exit status
    main = chris_plugin(parser=jpgs_toPng.parser(standalone=False), title="JPG to PNG")(jpgs_toPng)

The third is a ChRIS plugin: the tool carries the ``(options, inputdir, outputdir)`` signature ``@chris_plugin`` inspects, and runs when the plugin's entry point calls it. The decorator's keywords are the flags' defaults in every form, and the command line overrides them.

More than one stage shares a ``Tool``:

.. code:: python

    from pfdo import Tool

    tool = Tool(fileFilter="glob:*.dcm", analyzeFileIndex="f")

    @tool.analyze
    def series_toNifti(node: DirNode, read: StageResult) -> StageResult: ...

    @tool.save
    def manifest_write(node: DirNode, analyzed: StageResult) -> StageResult: ...

    tool("/data", "/out")

Underneath, a ``Pfdo`` subclass is built on the fly whose callbacks call the registered functions, so only the stages given exist and pfdo's rule that only overridden stages run applies unchanged. A tool that overrides the engine itself, as ``pfdo_run`` overrides how a job runs, is still a subclass.

pfdo and PathMapper
-------------------

The ChRIS plugin template's ``PathMapper`` is the tool a plugin author reaches for first, and for a per-file task with no reporting it is the right one. The same conversion, both ways:

.. code:: python

    mapper = PathMapper.file_mapper(inputdir, outputdir, glob="**/*.jpg", suffix=".png")
    for inputFile, outputFile in mapper:
        convert(inputFile, outputFile)

.. code:: python

    @analyze(fileFilter="glob:*.jpg", threads=4)
    def jpgs_toPng(node: DirNode, read: StageResult) -> StageResult:
        for name in read.files:
            convert(node.path / name, node.outputPath / Path(name).with_suffix(".png"))
        return StageResult(status=True, files=read.files)

What the two extra lines buy, and what they cost:

======================  ==========================================  ==========================================
                        PathMapper                                  pfdo
======================  ==========================================  ==========================================
Unit                    a file, or a leaf directory                 a directory with its filtered files
Selection               a glob and a Python filter, fixed in code   ``--fileFilter``, ``--dirFilter``, ``--maxDepth``, ``--analyzeFileIndex``, from the command line
Output path             mirrored, suffix swapped, parent created    mirrored, ``outputPath`` created, leaf template
Parallelism             yours: a ``ThreadPoolExecutor`` around it   ``--threads``
A failing item          raises out of the loop                      fails its directory; the run continues
What happened           nothing, unless you count                   ``RunResult``: per-directory ``StageResult``, counts, timing, JSON
Command line            yours                                       pfdo's flags, ``--json``, ``--man``, ``--version`` named after the tool
Dependencies            none beyond chris_plugin                    pfdo and pftree
What you write          the loop body                               a function returning ``StageResult``
======================  ==========================================  ==========================================

The cost is real: a file-wise task pays an inner loop over ``read.files``, every stage returns a record whether or not it has anything to say, and the frame is a thing to learn. The pay-off starts the moment the loop needs any one row of the table above, and the pl-dylld plugin shows where that moment comes: it uses ``PathMapper.dir_mapper_deep`` to get a directory unit for per-series work, then wraps the mapper in its own thread pool and its own log, which is the frame rebuilt by hand. ``docs/purpose.adoc`` has the longer comparison.

Changes in 6.2
--------------

- ``Tool`` and ``analyze``: a task attached by decorator, one stage or several, callable from Python, as a command, or as a ChRIS plugin's main.
- ``parser_build`` takes ``command`` and ``version``, so a tool built on pfdo answers ``--help`` and ``--version`` as itself.

Changes in 6.1
--------------

- ``pfdo.models`` re-exports pftree's ``DirNode``, ``StageResult``, ``ProcessResult``, ``RunResult`` and ``TreeOptions``.
- The default callbacks pass through; the demonstration pair runs only under ``--test``; only overridden stages run; overriding one is enough to process.

Changes in 6.0
--------------

- Built on ``pftree`` 4; ``pfmisc`` and ``pudb`` are no longer dependencies.
- The callbacks are ``inputRead_callback``, ``inputAnalyze_callback`` and ``outputSave_callback``, taking a ``DirNode`` and returning a ``StageResult``, not tuples and dicts.
- ``--analyzeFileIndex m`` picks the true middle file (index ``len // 2``); 5.x picked one past it for odd-length lists.
- An existing output file fails that directory and the run continues; 5.x stopped the loop and left the directory half written.
- ``--test`` maps to ``testRun``; ``pftree``'s own ``--test <seconds>`` is not exposed.
- ``main(argv)`` honours ``argv``; ``--version``, ``--man`` and ``--synopsis`` exit 0.
- Packaging is ``pyproject.toml`` only, published from CI on a ``v*`` tag.
