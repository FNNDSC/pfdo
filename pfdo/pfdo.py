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
from        pftree              import  pftree

try:
    from    .                   import __name__, __version__
except:
    from    __init__            import __name__, __version__


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
        self.__name__                   = __name__
        self.str_version                = __version__

        self.dp                         = None
        self.log                        = None
        self.tic_start                  = 0.0
        self.verbosityLevel             = -1

        # Declare/construct a delegate pf_tree
        self.pf_tree                    = pftree.pftree(self.args)

    def __init__(self, *args, **kwargs):
        """
        Constructor for pfdo.

        """
        self.args           = args[0]

        # The 'self' isn't fully instantiated, so
        # we call the following method on the class
        # directly.
        pfdo.declare_selfvars(self)
        self.str_desc       = self.args['str_desc']

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

    def fileListToAnalyze_determine(self, l_fileProbed):
        """
        Return the list of files to process, based on l_fileProbed
        and self.args['analyzeFileIndex']. This is useful for operations
        that might need only one file in an input directory to start but
        then once started will self consume multiple files independently
        of the external controller:

            "a":    "all" files.
            "m":    only the "middle" file in the file list
            "f":    only the "first" file in the file list
            "l":    only the "last" file in the file list
            "<N>":  only the file at index N in the file list. This index
                    can "wrap" in the positive and negative dir and can
                    exceed the actual list length (in which case it is
                    mapped correctly back into the original list).

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

        def middleIndex_find(l_lst):
            """
            Return the middle index in a list.
            If list has no length, return None.
            """
            middleIndex     = None
            if len(l_lst):
                if len(l_lst) == 1:
                    middleIndex = 0
                else:
                    middleIndex = round(len(l_lst)/2+0.01)
            return middleIndex

        def nIndex_find(l_lst, str_index):
            """
            This method attempts to find a numerical index within the
            file list, with support for +ve and -ve wrap around.

            If the str_index is non-numeric, return -1
            """
            index:  int = 0
            # pudb.set_trace()
            try:
                index   = int(str_index)
                if len(l_lst):
                    if index >= 0:
                        while index >= len(l_lst):
                            index -= len(l_lst)
                    else:
                        while abs(index) > len(l_lst):
                            index += len(l_lst)
                        index += len(l_lst)
                    return index
            except:
                pass
            return -1

        l_fileToAnalyze:    list    = []
        if len(l_fileProbed):
            if 'analyzeFileIndex' in self.args:
                if self.args['analyzeFileIndex'] == 'a': l_fileToAnalyze = l_fileProbed
                if self.args['analyzeFileIndex'] == 'f': l_fileToAnalyze.append(l_fileProbed[0])
                if self.args['analyzeFileIndex'] == 'l': l_fileToAnalyze.append(l_fileProbed[-1])
                if self.args['analyzeFileIndex'] == 'm':
                    if middleIndex_find(l_fileProbed) >= 0:
                        self.dp.qprint(l_fileProbed, level = 5)
                        l_fileToAnalyze.append(l_fileProbed[middleIndex_find(l_fileProbed)])
                nIndex  = nIndex_find(l_fileProbed, self.args['analyzeFileIndex'])
                if nIndex>=0:
                    l_fileToAnalyze.append(l_fileProbed[nIndex])
        return l_fileToAnalyze

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
            l_fileProbed        = self.fileListToAnalyze_determine(
                                    d_inputReadCallback['l_fileProbed']
                                )
            l_fileAnalyzed      = ['analyzed-%s' % x for x in l_fileProbed]
            b_status            = True
            filesAnalyzed      += len(l_fileAnalyzed)

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
                self.dp.qprint("saving: %s%s" % (str_outputPath, f), level = 5)
                filesSaved += 1

        return {
            'status':       b_status,
            'filesSaved':   filesSaved,
            'overwrite':    self.args['overwrite']
        }

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
            d_pftreeProbe   = self.pf_tree.run(timerStart = False)
            if d_pftreeProbe['status']:
                b_status    = d_pftreeProbe['status']
                if self.args['test']:
                    d_pftreeRun = self.testRun()
                    b_status    = d_pftreeRun['status']

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