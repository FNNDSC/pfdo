#!/usr/bin/env python3
#
# (c) 2022 Fetal-Neonatal Neuroimaging & Developmental Science Center
#                   Boston Children's Hospital
#
#              http://childrenshospital.org/FNNDSC/
#                        dev@babyMRI.org
#

import sys, os

try:
    from    .               import pfdo
    from    .               import __pkg, __version__
except:
    from pfdo               import pfdo
    from __init__           import __pkg, __version__
from    argparse            import RawTextHelpFormatter
from    argparse            import ArgumentParser
import  pudb

import  pfmisc
from    pfmisc._colors      import Colors
from    pfmisc              import other

import  pftree
from    pftree.__main__     import  package_CLIcore,        \
                                    package_IOcore,         \
                                    package_argSynopsisIO,  \
                                    package_argSynopsisCore,\
                                    parserIO,               \
                                    parserCore

str_desc = Colors.CYAN + f'''

                                  __      _
                                 / _|    | |
                          _ __  | |_   __| |  ___
                         | '_ \ |  _| / _` | / _ \ 
                         | |_) || |  | (_| || (_) |
                         | .__/ |_|   \__,_| \___/
                         | |
                         |_|



                          Path-File Do (something)

        Recursively walk down a directory tree and perform some operation
        on files in each directory (optionally filtered by some simple
        expression). Results of each operation are saved in output tree
        that  preserves the input directory structure.


                             -- version ''' + \
             Colors.YELLOW + __version__ + Colors.CYAN + ''' --

        'pfdo' is the base infrastructure app/class for walking down some
        dir tree, optionally finding and tagging files that conform to
        a simple filter, and running (something) on the files. This class
        provides the basic mechanism for using pfree in this manner and the
        (something) operation should be provided by a subclass of this base.

        As part of the "pf*" suite of applications, it is geared to IO as
        directories. Nested directory trees within some input directory
        are reconstructed in an output directory, preserving directory
        structure.

        In many ways, this module is a slight variation on 'pftree' on which
        it builds. It can be thought of as less of a descendent and more of a
        sibling.


''' + Colors.NO_COLOUR

package_CLIself = '''
        [--test]                                                                \\'''

package_argSynopsisSelf = """
        [--test]
        If specified, run the "dummy" internal callback loop triad. The test
        flow simply tags files in some inputDir tree and "touches" them to a
        reconstiuted tree in the output directory, prefixed with the text
        "analyzed-".
"""

def synopsis(ab_shortOnly = False):
    scriptName = os.path.basename(sys.argv[0])
    shortSynopsis =  """
    NAME

        pfdo

    SYNOPSIS

        pfdo \ """ + package_IOcore + package_CLIself +  package_CLIcore + """

    BRIEF EXAMPLE

        pfdo                                                                    \\
            --inputDir /var/www/html/data                                       \\
            --fileFilter jpg                                                    \\
            --outputDir /var/www/html/jpg                                       \\
            --threads 0 --printElapsedTime --test
    """

    description =  '''
    DESCRIPTION

        ``pfdo`` provides the base mechanism for navigating some arbitrary
        tree, providing the base hooks for operating on (possibly filtered)
        files in each directory, and saving results in an output tree that
        reflects the input tree topology.

    ARGS ''' + package_argSynopsisIO + package_argSynopsisSelf + package_argSynopsisCore + '''


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
            --inputDir $(pwd)/raw                                               \\
            --dirFilter 100307                                                  \\
            --outputDir $(pwd)/out --test --json                                \\
            --threads 0 --printElapsedTime

    Here, all files in (all) directories that contain the string ``100307``
    will be targetted.

    Finally the elapsed time and a JSON output are printed.

    '''

    if ab_shortOnly:
        return shortSynopsis
    else:
        return shortSynopsis + description

parserSelf  = ArgumentParser(description        = 'Self specific',
                             formatter_class    = RawTextHelpFormatter,
                             add_help           = False)

parserSelf.add_argument("--test",
                    help    = "test",
                    dest    = 'test',
                    action  = 'store_true',
                    default = False)

def main(argv=None):
    parser  = ArgumentParser(description        = str_desc,
                             formatter_class    = RawTextHelpFormatter,
                             parents            = [parserCore, parserIO, parserSelf])
    args = parser.parse_args()
    if args.man or args.synopsis:
        print(str_desc)
        if args.man:
            str_help     = synopsis(False)
        else:
            str_help     = synopsis(True)
        print(str_help)
        return 1

    if args.b_version:
        print("Name:    %s\nVersion: %s" % (__pkg.name, __version__))
        return 1

    args.str_version    = __version__
    args.str_desc       = synopsis(True)

    pf_do               = pfdo.pfdo(vars(args))

    # And now run it!
    d_pfdo              = pf_do.run(timerStart = True)

    if args.printElapsedTime:
        pf_do.dp.qprint(
                "Elapsed time = %f seconds" %
                d_pfdo['runTime']
        )

    return 0

if __name__ == "__main__":
    sys.exit(main())