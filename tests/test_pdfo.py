

from pathlib import Path
from argparse import ArgumentParser, Namespace, ArgumentDefaultsHelpFormatter

# import sys, os
# sys.path.insert(1, os.path.join(os.path.dirname(__file__), '../'))

from    pfdo import pfdo as libpfdo
from    pfdo import __main__ as binpfdo

def test_main(tmp_path: Path):
    """
    Simulated test run of the app.
    """
    inputdir = tmp_path / 'incoming'
    outputdir = tmp_path / 'outgoing'
    inputdir.mkdir()
    outputdir.mkdir()

    options = binpfdo.parser(['--test'])


    pf_do   = pfdo.pfdo(vars(options))
    d_pdfo  = pf_do.run(timerStart = True)

    expected_output_file = outputdir / 'bar.txt'
    assert expected_output_file.exists()
    assert expected_output_file.read_text() == 'did nothing successfully!'