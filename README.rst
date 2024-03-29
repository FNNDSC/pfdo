pfdo
==================

.. image:: https://badge.fury.io/py/pfdo.svg
    :target: https://badge.fury.io/py/pfdo

.. image:: https://travis-ci.org/FNNDSC/pfdo.svg?branch=master
    :target: https://travis-ci.org/FNNDSC/pfdo

.. image:: https://img.shields.io/badge/python-3.5%2B-blue.svg
    :target: https://badge.fury.io/py/pfdo

.. contents:: Table of Contents


Quick Overview
--------------

-  ``pfdo`` demonstrates how to use ``pftree`` to transverse directory trees and execute a specific analysis at each directory level (that optionally contains files of interest).

Overview
--------

``pfdo`` is a reference / base class application that is typically used as a component for constructing more complex behavioured functions. The application leverages the ``pfree`` callback coding contract to target a specific directory with specific files in an arbitrary file tree.

For example, imagine a nested tree of JPG image files and imagine some application that processes JPGs (rotates, increases size, etc). Using a suitably sub-classed ``pfdo`` (for example pfdo_imgconvert), a developer is able to apply some necessary processing to the files of interest irrespective of where in some input tree structure the files exist.

Moreover, the results of the processing are stored in an output directory, in an output tree, that reflects the topology of the input tree.


Installation
------------

Dependencies
~~~~~~~~~~~~

The following dependencies are installed on your host system/python3 virtual env (they will also be automatically installed if pulled from pypi):

-  ``pfmisc`` (various misc modules and classes for the pf* family of objects)
-  ``pftree`` (create a dictionary representation of a filesystem hierarchy)

Using ``PyPI``
~~~~~~~~~~~~~~

The best method of installing this script and all of its dependencies is
by fetching it from PyPI

.. code:: bash

        pip3 install pfdo

Command line arguments
----------------------

.. code:: html

        --inputDir <inputDir>
        Input directory to examine. The downstream nested structure of this
        directory is examined and recreated in the <outputDir>.

        [--outputDir <outputDir>]
        The directory to contain a tree structure identical to the input
        tree structure, and which contains all output files from the
        per-input-dir processing.

        [--test]
        If specified, run the "dummy" internal callback loop triad. The test
        flow simply tags files in some inputDir tree and "touches" them to a
        reconstiuted tree in the output directory, prefixed with the text
        "analyzed-".


        [--maxdepth <dirDepth>]
        The maximum depth to descend relative to the <inputDir>. Note, that
        this counts from zero! Default of '-1' implies transverse the entire
        directory tree.

        [--relativeDir]
        A flag argument. If passed (i.e. True), then the dictionary key values
        are taken to be relative to the <inputDir>, i.e. the key values
        will not contain the <inputDir>; otherwise the key values will
        contain the <inputDir>.

        [--inputFile <inputFile>]
        An optional <inputFile> specified relative to the <inputDir>. If
        specified, then do not perform a directory walk, but target this
        specific file.

        [--fileFilter <someFilter1,someFilter2,...>]
        An optional comma-delimated string to filter out files of interest
        from the <inputDir> tree. Each token in the expression is applied in
        turn over the space of files in a directory location according to a
        logical operation, and only files that contain this token string in
        their filename are preserved.

        [--filteFilterLogic AND|OR]
        The logical operator to apply across the fileFilter operation. Default
        is OR.

        [--dirFilter <someFilter1,someFilter2,...>]
        An additional filter that will further limit any files to process to
        only those files that exist in leaf directory nodes that have some
        substring of each of the comma separated <someFilter> in their
        directory name.

        [--dirFilterLogic AND|OR]
        The logical operator to apply across the dirFilter operation. Default
        is OR.

        [--outputLeafDir <outputLeafDirFormat>]
        If specified, will apply the <outputLeafDirFormat> to the output
        directories containing data. This is useful to blanket describe
        final output directories with some descriptive text, such as
        'anon' or 'preview'.

        This is a formatting spec, so

            --outputLeafDir 'preview-%%s'

        where %%s is the original leaf directory node, will prefix each
        final directory containing output with the text 'preview-' which
        can be useful in describing some features of the output set.

        [--threads <numThreads>]
        If specified, break the innermost analysis loop into <numThreads>
        threads. Please note the following caveats:

            * Only thread if you have a high CPU analysis loop. Note that
              the input file read and output file write loops are not
              threaded -- only the analysis loop is threaded. Thus, if the
              bulk of execution time is in file IO, threading will not
              really help.

            * Threading will change the nature of the innermost looping
              across the problem domain, with the result that *all* of the
              problem data will be read into memory! That means potentially
              all the target input file data across the entire input directory
              tree.

        [--json]
        If specified, do a JSON dump of the entire return payload.

        [--followLinks]
        If specified, follow symbolic links.

        [--overwrite]
        If specified, allow for overwriting of existing files

        [--man]
        Show full help.

        [--synopsis]
        Show brief help.

        [--verbosity <level>]
        Set the app verbosity level. This ranges from 0...<N> where internal
        log messages with a level=<M> will only display if M <= N. In this
        manner increasing the level here can be used to show more and more
        debugging info, assuming that debug messages in the code have been
        tagged with a level.

Examples
--------

Filtering
~~~~~~~~~

The ``--fileFilter`` and ``--dirFilter`` apply a filter to the string space of file and directory representations, reducing the original space of

.. code:: bash

    "<path>": [<"filesToProcess">]

to only those paths and files that are relevant to the operation being performed. Two filters are understood, a ``fileFilter`` that filters filenames that match any of the passed search substrings from the CLI ``--fileFilter``, and a ``dirFilter`` that filters directories whose leaf nodes match any of the passed ``--dirFilter`` substrings.

The effect of these filters is hierarchical. First, the ``fileFilter`` is applied across the space of files for a given directory path. Each comma separated token is used as a substring search across the file name - in any order. The token search is by default a logical OR operation. Thus, a ``--fileFilter`` of ``png,jpg,body`` will filter all files that have the substrings of ``png`` _OR_ ``jpg`` _OR_ ``body`` anywhere in their filenames. This operation can be changed to a logical AND with a ``--fileFilterLogic AND`` - in which case a ``--fileFilter aparc,mgz,aseg`` will filter all files that contain ``aparc`` _AND_ ``aseg`` _AND_ ``mgz`` in their names. Note that mixing boolean logic is not supported at this time.

Next, if a ``dirFilter`` has been specified, the current string path corresponding to the filenames being filtered is considered. Each string in the comma separated ``dirFilter`` list is exacted, and if the basename of the working directory contains the filter substring, the (filtered) files are conserved. If the basename of the working directory does not contain any of the ``dirFilter`` substrings, the file list is discarded. Similarly ``dirFilterLogic`` specifies the logical operation to perform on the directory filter tokens.

Thus, a ``--dirFilter 100307,100556`` and a ``--fileFilter png,jpg`` will reduce the space of files to process to ONLY files that have a parent directory of ``100307`` OR ``100556`` AND that contain either the string ``png`` OR ``jpg`` in their file names.

Processing
~~~~~~~~~~

Run down a directory tree and touch all the files in the input tree that are ``jpgs`` to similar locations in the output directory:

.. code:: bash

        pfdo                                                                    \
            --inputDir /var/www/html/data --fileFilter jpg                      \
            --outputDir /tmp/jpg --test --json                                  \
            --threads 0 --printElapsedTime


The above will find all files in the tree structure rooted at ``/var/www/html/`` data that also contain the string ``jpg`` anywhere in the filename. For each file found, a corresponding file will be touched in the output directory, in the same tree location as the original input. This touched file will be prefixed with the
string ``analyzed-``.

.. code:: bash

        pfdo                                                                \
            --inputDir $(pwd)/raw  --dirFilter 100307 --fileFilter ""       \
            --outputDir $(pwd)/out --test --json                            \
            --threads 0 --printElapsedTime

Here, all files in (all) directories that contain the substring ``100307`` will be targetted.

Finally the elapsed time and a JSON output are printed.

*-30-*

