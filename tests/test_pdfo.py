from pathlib import Path
from argparse import ArgumentParser, Namespace, ArgumentDefaultsHelpFormatter
import sys
from unittest.mock import patch


# import sys, os
# sys.path.insert(1, os.path.join(os.path.dirname(__file__), '../'))

from    pfdo import pfdo
from    pfdo import __main__ as main

import  pudb

def test_main(tmp_path: Path):
    """
    Simulated test run of the app.
    """
    pudb.set_trace()
    # inputdir    = tmp_path / 'incoming'
    outputdir   = tmp_path / 'outgoing'
    Path(tmp_path / 'incoming/A/a').mkdir(parents = True, exist_ok = True)
    Path(tmp_path / 'incoming/B/b').mkdir(parents = True, exist_ok = True)
    inputdir    = tmp_path / 'incoming'
    targetFiles     = {
        inputdir / 'A' / 'a' / 'aseg.mgz',
        inputdir / 'A' / 'a' / 'aseg+aparc.mgz',
        inputdir / 'A' / 'a' / 'aseg2009+aparc.mgz',
        inputdir / 'A' / 'a' / 'aseg2009.txt',
        inputdir / 'B' / 'b' / 'mri.mgz',
        inputdir / 'B' / 'b' / 'mri+aparc.mgz',
        inputdir / 'B' / 'b' / 'aseg2009+mri.mgz',
        inputdir / 'B' / 'b' / 'mri.txt',
    }
    for target in targetFiles:
        target.touch()

    outputdir.mkdir()

    with patch("sys.argv", ["main",
                "--test",
                "--verbosity",
                "5",
                "--fileFilter aparc,mgz",
                "--fileFilterLogic AND",
                "-I", str(inputdir),
                "-O", str(outputdir)]):

        args    = main.parser.parse_args()

        pf_do   = pfdo.pfdo(vars(args))
        d_pdfo  = pf_do.run(timerStart = True)

        expected_output_file = outputdir / 'A' / 'a' / 'analyzed-aseg.mgz'
        assert expected_output_file.exists()
