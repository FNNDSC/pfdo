# System imports
import      os
import      json
import      pathlib

# Project specific imports
import      pfmisc
from        pfmisc._colors      import  Colors
from        pfmisc              import  other
from        pfmisc              import  error

import      pudb
import      pftree

class pfdo(object):
    """

    A base class for navigating down a dir tree and providing
    hooks for some (subclass) analysis

    """

    _dictErr = {
        'outputDirFail'   : {
            'action'        : 'trying to check on the output directory, ',
            'error'         : 'directory not specified. This is a *required* input.',
            'exitCode'      : 1},
        'outputFileExists'   : {
            'action'        : 'attempting to write an output file, ',
            'error'         : 'it seems a file already exists. Please run with --overwrite to force overwrite.',
            'exitCode'      : 2}
        }


    def declare_selfvars(self):
        """
        A block to declare self variables
        """

        #
        # Object desc block
        #
        self.str_desc                   = ''
        self.__name__                   = "pfdo"

        self.dp                         = None
        self.log                        = None
        self.tic_start                  = 0.0
        self.verbosityLevel             = -1
        self.maxDepth                   = -1

        # Declare pf_tree
        self.pf_tree    = pftree.pftree(
                inputDir                = self.args['inputDir'],
                maxDepth                = self.maxDepth,
                inputFile               = self.args['inputFile'],
                outputDir               = self.args['outputDir'],
                outputLeafDir           = self.args['outputLeafDir'],
                threads                 = int(self.args['threads']),
                verbosity               = int(self.args['verbosity']),
                followLinks             = bool(self.args['followLinks']),
                relativeDir             = True
        )

    def __init__(self, *args, **kwargs):
        """
        Constructor for pftreeDo.

        """
        self.args           = args[0]

        # The 'self' isn't fully instantiated, so
        # we call the following method on the class
        # directly.
        pfdo.declare_selfvars(self)

        self.dp             = pfmisc.debug(
                                 verbosity   = int(self.args['verbosity']),
                                 within      = self.__name__
                             )

    def inputReadCallback(self, *args, **kwargs) -> dict:
        """
        Callback stub for reading files from specific directory.

        This current method is really just the null case and exists
        merely to show/demonstrate how to use such a callback. Here,
        this method merely makes a copy/list of the input list of
        incoming files.

        In almost all cases, this method should be overloaded by a
        descendant class.
        """
        str_path        : str       = ''
        l_fileProbed    : list      = []
        l_fileRead      : list      = []
        b_status        : bool      = True
        filesRead       : int       = 0

        for k, v in kwargs.items():
            if k == 'l_file':   l_file      = v
            if k == 'path':     str_path    = v

        if len(args):
            at_data         = args[0]
            str_path        = at_data[0]
            l_fileProbed    = at_data[1]

        for f in l_fileProbed:
            self.dp.qprint("Adding file: %s/%s to list" % (str_path, f), level = 5)
            l_fileRead.append(f)
            filesRead       += 1

        if not len(l_fileRead): b_status = False

        return {
            'status':           b_status,
            'l_fileProbed':     l_fileProbed,
            'str_path':         str_path,
            'l_fileRead':       l_fileRead,
            'filesRead':        filesRead
        }

    def inputAnalyzeCallback(self, *args, **kwargs):
        """
        Callback stub for doing actual work on the read data.
        Here, we simply prepend the string 'analyzed-' to each
        filename in the input list.

        This dummy method is mostly for illustration.
        """
        b_status            : bool  = False
        l_fileProbed        : list  = []
        l_fileAnalyzed      : list  = []
        filesAnalyzed       : int   = 0
        d_inputReadCallback : dict  = {}

        for k, v in kwargs.items():
            if k == 'path':         str_path    = v

        if len(args):
            at_data             = args[0]
            str_path            = at_data[0]
            d_inputReadCallback = at_data[1]

        if 'l_fileProbed' in d_inputReadCallback.keys():
            l_fileProbed    = d_inputReadCallback['l_fileProbed']
            l_fileAnalyzed  = ['analyzed-%s' % x for x in l_fileProbed]
            b_status        = True
            filesAnalyzed  += len(l_fileAnalyzed)

        return {
            'status':           b_status,
            'str_path':         str_path,
            'l_fileAnalyzed':   l_fileAnalyzed,
            'filesAnalyzed':    filesAnalyzed
        }

    def outputSaveCallback(self, *args, **kwags) -> dict:
        """
        Callback stub for saving outputs. Here, we simply
        "touch" each file in the analyzed list to the output
        tree.

        This dummy method is mostly for illustration.
        """

        str_outputPath          : str   = ""
        d_inputAnalyzeCallback  : dict  = {}
        filesSaved              : int   = 0
        b_status                : bool  = False
        str_fileToSave          : str   = ""

        if len(args):
            at_data                 = args[0]
            str_outputPath          = at_data[0]
            d_inputAnalyzeCallback  = at_data[1]

        if 'l_fileAnalyzed' in d_inputAnalyzeCallback.keys() and \
        len(str_outputPath):
            other.mkdir(self.args['outputDir'])
            other.mkdir(str_outputPath)
            for f in d_inputAnalyzeCallback['l_fileAnalyzed']:
                str_fileToSave  = os.path.join(str_outputPath, f)
                if os.path.exists(str_fileToSave):
                    if self.args['overwrite']: os.remove(str_fileToSave)
                    else:
                        error.warn(self, 'outputFileExists', drawBox = True)
                        b_status = False
                        break
                os.mknod('%s/%s' % (str_outputPath, f))
                b_status                = True
                self.dp.qprint("saving: %s/%s" % (str_outputPath, f), level = 5)
                filesSaved += 1

        return {
            'status':       b_status,
            'filesSaved':   filesSaved,
            'overwrite':    self.args['overwrite']
        }

    def FS_filter(self, at_data, *args, **kwargs) -> dict:
        """
        Apply a filter to the string space of file and directory
        representations.

        The purpose of this method is to reduce the original space of

                        "<path>": [<"filesToProcess">]

        to only those paths and files that are relevant to the operation being
        performed. Two filters are understood, a `fileFilter` that filters
        filenames that match any of the passed search substrings from the CLI
        `--fileFilter`, and a`dirFilter` that filters directories whose
        leaf node match any of the passed `--dirFilter` substrings.

        The effect of these filters is hierarchical. First, the `fileFilter`
        is applied across the space of files for a given directory path. By
        default, the files are subject to a logical OR operation across th
        comma separated filter argument. Thus, a `fileFilter` of "png,jpg,body"
        will filter all files that have the substrings of "png" OR "jpg" OR
        "body" in their filenames. This logical operation can be set with
        "--fileFilterLogic AND" to use AND instead. In such a case, a filter
        of "aparc,mgz" will filter all files that contain "aparc" AND "mgz"
        in their filenames.

        Next, if a `dirFilter` has been specified, the current string path
        corresponding to the filenames being filtered is considered. Each
        string in the comma separated `dirFilter` list is exacted, and if
        the basename of the working directory contains the filter substring,
        the (filtered) files are conserved. If the basename of the working
        directory does not contain any of the `dirFilter` substrings, the
        file list is discarded.

        Thus, a `dirFilter` of "100307,100556" and a fileFilter of "png,jpg"
        will reduce the space of files to process to ONLY files that have
        a parent directory of "100307" OR "100556" AND that contain either the
        string "png" OR "jpg" in their file names.
        """

        b_status    : bool      = True
        l_file      : list      = []
        l_dirHits   : list      = []
        l_dir       : list      = []
        str_path    : str       = at_data[0]
        al_file     : list      = at_data[1]

        if len(self.args['fileFilter']):
            if self.args['fileFilterLogic'].upper == 'OR':
                al_file     = [x                                            \
                            for y in self.args['fileFilter'].split(',')     \
                                for x in al_file if y in x]
            else:
                for y in self.args['fileFilter'].split(','):
                    al_file = [x for x in al_file if y in x]

        if len(self.args['dirFilter']):
            l_dirHits   = [os.path.basename(str_path)                       \
                            for y in self.args['dirFilter'].split(',')      \
                                if y in os.path.basename(str_path)]
            if len(l_dirHits):
                # Remove any duplicates in the l_dirHits: duplicates can occur
                # if the tokens in the filter expression map more than once
                # into the leaf node in the <str_path>, as a path that is
                #
                #               /some/dir/in/the/space/1234567
                #
                # and a search filter on the dirspace of "123,567"
                [l_dir.append(x) for x in l_dirHits if x not in l_dir]
            else:
                # If no dir hits for this dir, then we zero out the
                # file filter
                al_file = []

        if len(al_file):
            al_file.sort()
            l_file      = al_file
            b_status    = True
        else:
            self.dp.qprint( "No valid files to analyze found in path %s!" %
                            str_path, comms = 'warn', level = 5)
            l_file      = None
            b_status    = False
        return {
            'status':   b_status,
            'l_file':   l_file
        }

    def filterFileHitList(self) -> dict:
        """
        Entry point for filtering the file filter list
        at each directory node.
        """
        d_filterFileHitList = self.pf_tree.tree_process(
                        inputReadCallback       = None,
                        analysisCallback        = self.FS_filter,
                        outputWriteCallback     = None,
                        applyResultsTo          = 'inputTree',
                        applyKey                = 'l_file',
                        persistAnalysisResults  = True
        )
        return d_filterFileHitList

    def env_check(self, *args, **kwargs) -> dict:
        """
        This method provides a common entry for any checks on the
        environment (input / output dirs, etc)
        """
        b_status    : bool  = True
        str_error   : str   = ''

        if not len(self.args['outputDir']):
            b_status = False
            str_error   = 'output directory not specified.'
            self.dp.qprint(str_error, comms = 'error')
            error.warn(self, 'outputDirFail', drawBox = True)

        return {
            'status':       b_status,
            'str_error':    str_error
        }

    def ret_dump(self, d_ret, **kwargs):
        """
        JSON print results to console (or caller)
        """
        b_print     = True
        for k, v in kwargs.items():
            if k == 'JSONprint':    b_print     = bool(v)
        if b_print:
            print(
                json.dumps(
                    d_ret,
                    indent      = 4,
                    sort_keys   = True
                )
        )

    def testRun(self) -> dict:
        """
        Run the internal (mostly dummy) callbacks infrastructure.

        Note that the return json of each callback is available to
        the next callback in the queue as the second tuple value in
        the first argument passed to the callback.

        This is presented largely for informational/instructional
        purposes.
        """
        d_testRun : dict    = {}

        d_testRun   = self.pf_tree.tree_process(
                            inputReadCallback       = self.inputReadCallback,
                            analysisCallback        = self.inputAnalyzeCallback,
                            outputWriteCallback     = self.outputSaveCallback,
                            persistAnalysisResults  = False
        )
        return d_testRun

    def run(self, *args, **kwargs) -> dict:
        """
        This base run method should be called by any descendent classes
        since this contains the calls to the first `pftree` core as well
        as any (overloaded) file filtering.
        """
        b_status        : bool  = False
        b_timerStart    : bool  = False
        d_env           : dict  = {}
        d_filter        : dict  = {}
        d_pftreeProbe   : dict  = {}
        d_pftreeRun     : dict  = {}
        b_JSONprint     : bool  = True

        self.dp.qprint(
                "Starting pfdo run... (please be patient while running)",
                level = 1
        )

        for k, v in kwargs.items():
            if k == 'timerStart':   b_timerStart    = bool(v)
            if k == 'JSONprint':    b_JSONprint     = bool(v)

        if b_timerStart:    other.tic()

        d_env = self.env_check()
        if d_env['status']:
            # We change to the inputDir so as to get a relative
            # tree listing structure.
            str_startDir    = os.getcwd()
            os.chdir(self.args['inputDir'])
            d_pftreeProbe   = self.pf_tree.run(timerStart = False)
            if d_pftreeProbe['status']:
                b_status    = d_pftreeProbe['status']
                if len(self.args['fileFilter']) or len(self.args['dirFilter']):
                    d_filter    = self.filterFileHitList()
                    b_status    = d_filter['status']
                if self.args['test']:
                    d_pftreeRun = self.testRun()
                    b_status    = d_pftreeRun['status']
            os.chdir(str_startDir)

        d_ret = {
            'status':           b_status,
            'd_env':            d_env,
            'd_pftreeProbe':    d_pftreeProbe,
            'd_filter':         d_filter,
            'd_pftreeRun':      d_pftreeRun,
            'runTime':          other.toc()
        }

        if self.args['json'] and b_JSONprint:
            self.ret_dump(d_ret, **kwargs)
        else:
            self.dp.qprint('Returning from pfdo base class run...', level = 1)

        return d_ret