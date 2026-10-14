"""The ``pfdo`` command line and its manual.

``pfdo`` on its own walks a tree, applies the filters, and with ``--test`` runs the
base class's demonstration callbacks. Its parser and manual are assembled from
pftree's parts plus pfdo's own, and are themselves exposed in parts so a package
built on pfdo can assemble its own.

Key components:
    - CLI_SELF, ARGS_SYNOPSIS_SELF, EXAMPLES: pfdo's manual pieces
    - CLI_FULL, CLI_DS, ARGS_SYNOPSIS_FULL, ARGS_SYNOPSIS_DS: the assembled pieces,
      standalone and ChRIS-DS style
    - synopsis: the manual text for a command built on pfdo
    - manual_build: the page, rendered through ``pftree.manual``
    - parserSelf_build / parser_build: the argument parsers
    - main: the entry point, honouring an explicit ``argv``

Typical usage:
    pfdo --inputDir /data --outputDir /tmp/out --fileFilter jpg --test --json
    pfdo --man

Dependencies:
    - pftree (its CLI parts and manual renderer)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from pftree.__main__ import (
    ARGS_SYNOPSIS_CORE,
    ARGS_SYNOPSIS_DS,
    ARGS_SYNOPSIS_IO,
    CLI_CORE,
    CLI_DS_IO,
    CLI_IO_CORE,
    logging_configure,
    parserCore_build,
    parserIO_build,
)
from pftree.manual import Manual, manual_print
from pftree.models import RunResult

from pfdo import __version__
from pfdo.models import PfdoOptions
from pfdo.pfdo import Pfdo

BANNER_ART: str = r"""

                                  __      _
                                 / _|    | |
                          _ __  | |_   __| |  ___
                         | '_ \ |  _| / _` | / _ \
                         | |_) || |  | (_| || (_) |
                         | .__/ |_|   \__,_| \___/
                         | |
                         |_|

"""

BANNER_TITLE: str = "Path-File Do (something)"

BANNER_TEXT: str = """
                          Path-File Do (something)

        Recursively walk down a directory tree and perform some operation
        on files in each directory (optionally filtered by some simple
        expression). Results of each operation are saved in output tree
        that  preserves the input directory structure.

                             -- version {version} --

        'pfdo' is the base infrastructure app/class for walking down some
        dir tree, optionally finding and tagging files that conform to
        a simple filter, and running (something) on the files. This class
        provides the basic mechanism for using pftree in this manner and the
        (something) operation should be provided by a subclass of this base.

        As part of the "pf*" suite of applications, it is geared to IO as
        directories. Nested directory trees within some input directory
        are reconstructed in an output directory, preserving directory
        structure.

        In many ways, this module is a slight variation on 'pftree' on which
        it builds. It can be thought of as less of a descendent and more of a
        sibling.

"""

CLI_SELF: str = """
        [--analyzeFileIndex <a|f|l|m|N>]                                        \\
        [--test]                                                                \\"""

ARGS_SYNOPSIS_SELF: str = """
        [--test]
        If specified, run the "dummy" internal callback loop triad. The test
        flow simply tags files in some inputDir tree and "touches" them to a
        reconstituted tree in the output directory, prefixed with the text
        "analyzed-". An output file that already exists stops that directory
        unless --overwrite is given.

        [--analyzeFileIndex <a|f|l|m|N>]
        An optional string to further "filter" the list of files that have
        been detected to analyze. This is useful for certain operations
        that might need only one file in an input directory to start but
        then once started will self consume multiple files independently
        of the external controller. The default is "a" which implies
        *ALL* files in a given directory. The set of valid values:

            "a":    "all" files.
            "m":    only the "middle" file in the file list
            "f":    only the "first" file in the file list
            "l":    only the "last" file in the file list
            "<N>":  only the file at index N in the file list. This index
                    can "wrap" in the positive and negative direction and
                    can exceed the actual list length (in which case it is
                    mapped back into the original list).

                    Pedantically, in the negative direction:
                        '-1' will mean the last file, while
                        -<listLen> will mean the first file again
                        -<listLen+1> will mean the last file again
                        etc...
                    and in the positive direction:
                        <listLen> will mean the first file
                        <listLen>*2 will mean the first file
                        etc...
"""

EXAMPLES: str = """

    EXAMPLES

    Perform a `pfdo` down some input directory:

        pfdo                                                                    \\
            --inputDir /var/www/html/data                                       \\
            --fileFilter jpg                                                    \\
            --outputDir /tmp/jpg                                                \\
            --test --json                                                       \\
            --threads 0 --printElapsedTime

    The above will find all files in the tree structure rooted at
    /var/www/html/data that also contain the string "jpg" anywhere
    in the filename. For each file found, a corresponding file will
    be touched in the output directory, in the same tree location as
    the original input. This touched file will be prefixed with the
    string "analyzed-".

        pfdo                                                                    \\
            --inputDir $PWD/raw                                                 \\
            --dirFilter 100307                                                  \\
            --outputDir $PWD/out --test --json                                  \\
            --analyzeFileIndex m                                                \\
            --threads 0 --printElapsedTime

    Here, only the middle file in (all) directories whose path contains
    the string ``100307`` will be targetted.

    Finally the elapsed time and a JSON output are printed.

"""

CLI_FULL: str = CLI_IO_CORE + CLI_SELF + CLI_CORE
ARGS_SYNOPSIS_FULL: str = ARGS_SYNOPSIS_IO + ARGS_SYNOPSIS_SELF + ARGS_SYNOPSIS_CORE
CLI_DS: str = CLI_DS_IO + CLI_SELF + CLI_CORE
ARGS_SYNOPSIS_DS: str = ARGS_SYNOPSIS_DS + ARGS_SYNOPSIS_SELF + ARGS_SYNOPSIS_CORE

DESCRIPTION: str = """
    DESCRIPTION

        ``pfdo`` provides the base mechanism for navigating some arbitrary
        tree, providing the base hooks for operating on (possibly filtered)
        files in each directory, and saving results in an output tree that
        reflects the input tree topology.

        A subclass overrides the inputAnalyze_callback and outputSave_callback
        methods (each receives the DirNode for a directory and returns a
        StageResult) and sets processAlways; ``pfdo`` itself only runs its
        demonstration callbacks under --test.
"""


def synopsis(shortOnly: bool = False, command: str = "pfdo") -> str:
    """Assemble the manual text.

    Args:
        shortOnly: NAME, SYNOPSIS and a brief example only.
        command: the command name shown, for a package built on pfdo.

    Returns:
        The manual text, without the banner.
    """
    shortSynopsis: str = (
        f"""
    NAME

        {command}

    SYNOPSIS

        {command} \\"""
        + CLI_FULL
        + f"""

    BRIEF EXAMPLE

        {command}                                                                    \\
            --inputDir /var/www/html/data                                       \\
            --fileFilter jpg                                                    \\
            --outputDir /var/www/html/jpg                                       \\
            --threads 0 --printElapsedTime --test
    """
    )
    if shortOnly:
        return shortSynopsis
    return shortSynopsis + DESCRIPTION + "\n    ARGS " + ARGS_SYNOPSIS_FULL + EXAMPLES


def manual_build() -> Manual:
    """The pfdo manual page.

    Returns:
        The page, with both synopses assembled.
    """
    return Manual(
        command="pfdo",
        art=BANNER_ART,
        title=BANNER_TITLE,
        text=BANNER_TEXT,
        version=__version__,
        synopsisShort=synopsis(shortOnly=True),
        synopsisFull=synopsis(shortOnly=False),
    )


def parserSelf_build() -> argparse.ArgumentParser:
    """pfdo's own options.

    Returns:
        A parent parser with ``--test`` and ``--analyzeFileIndex``.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--test", dest="testRun", action="store_true", help="run the demonstration callbacks")
    parser.add_argument(
        "--analyzeFileIndex",
        dest="analyzeFileIndex",
        default="a",
        help="which files per directory the analyze step gets: a (all), f, l, m, or an index",
    )
    return parser


def parser_build(
    standalone: bool = True, command: str = "pfdo", version: str = __version__
) -> argparse.ArgumentParser:
    """Assemble the full parser.

    Args:
        standalone: include ``--inputDir`` / ``--outputDir``. A ChRIS DS plugin
            passes False and adds its own positional directories.
        command: the program's name, for ``--help`` and ``--version``; a tool built
            on pfdo passes its own.
        version: the version ``--version`` prints, with ``command``.

    Returns:
        The parser; ``--help`` is the quick reference and points at ``--man``.
    """
    parents: list[argparse.ArgumentParser] = [parserCore_build(command, version), parserSelf_build()]
    if standalone:
        parents.insert(0, parserIO_build())
    return argparse.ArgumentParser(
        prog=command,
        description=(
            f"Walk a directory tree and do something in every directory. Full manual: {command} --man"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=parents,
    )


def options_fromArgs(args: argparse.Namespace) -> PfdoOptions:
    """Turn parsed arguments into options.

    Args:
        args: the parser's Namespace.

    Returns:
        PfdoOptions with every known field applied.
    """
    return PfdoOptions.fromDict(vars(args))


def result_report(args: argparse.Namespace, result: RunResult) -> None:
    """Print what the arguments asked for.

    Args:
        args: the parsed arguments.
        result: the run's result.
    """
    if args.json:
        print(json.dumps(result.toDict(), indent=4, sort_keys=True))
    if args.printElapsedTime:
        print(f"Elapsed time = {result.runTime:.6f} seconds")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command.

    Args:
        argv: arguments without the program name; ``None`` reads ``sys.argv``.

    Returns:
        The exit code: 0 on success, 1 when the run failed, 2 on bad arguments.
    """
    parser: argparse.ArgumentParser = parser_build()
    args: argparse.Namespace = parser.parse_args(argv)
    if args.man or args.synopsis:
        manual_print(manual_build(), shortOnly=not args.man)
        return 0
    if not args.inputDir:
        parser.error("--inputDir is required")
    try:
        options: PfdoOptions = options_fromArgs(args)
    except ValueError as err:
        parser.error(str(err))
    logging_configure(options.verbosity)
    result: RunResult = Pfdo(options).run()
    result_report(args, result)
    if result.error:
        print(result.error, file=sys.stderr)
    return 0 if result.status else 1


if __name__ == "__main__":
    sys.exit(main())
