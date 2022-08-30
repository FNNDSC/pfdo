from pathlib import Path
from argparse import ArgumentParser, Namespace, ArgumentDefaultsHelpFormatter
import sys

from    pfdo import pfdo
from    pfdo import __main__ as main

import  pudb

def test_main(tmp_path: Path):
    """
    Simulated test run of the app.
    """
    # pudb.set_trace()
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

    args    = main.parser.parse_args([
                "--test",
                "--verbosity",
                "5",
                "--fileFilter",
                "aparc,mgz",
                "--fileFilterLogic",
                "AND",
                "-I", str(inputdir),
                "-O", str(outputdir)
            ])

    pf_do   = pfdo.pfdo(vars(args))
    d_pdfo  = pf_do.run(timerStart = True)

    expected_output_file1 = outputdir / 'A' / 'a' / 'analyzed-aseg+aparc.mgz'
    expected_output_file2 = outputdir / 'A' / 'a' / 'analyzed-aseg2009+aparc.mgz'
    expected_output_file3 = outputdir / 'B' / 'b' / 'analyzed-mri+aparc.mgz'

    assert expected_output_file1.exists()
    assert expected_output_file2.exists()
    assert expected_output_file3.exists()
