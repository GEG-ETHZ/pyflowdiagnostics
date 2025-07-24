import pytest
import numpy as np
from os.path import join
from numpy.testing import assert_allclose

from . import get_data
import pyflowdiagnostics
import pyflowdiagnostics.flow_diagnostics as pfd

# Get input data
SPE10_DIR = get_data.get_input_data(version="2025-07-23")

# Get regression data
DATA = get_data.get_regression_data()


def test_status_quo_python():

    fd = pfd.FlowDiagnostics(join(SPE10_DIR, "SPE10.DATA"))
    fd.execute(time_step_id=1)

    # Read in result
    tracer = np.loadtxt(
        join(SPE10_DIR, 'SPE10.fdout/Tracer_1.csv'),
        skiprows=1, delimiter=',', dtype=np.single,
    )
    f_phi = np.loadtxt(
        join(SPE10_DIR, 'SPE10.fdout/F_Phi_1.csv'),
        skiprows=1, delimiter=',', dtype=np.single,
    )

    # Check them
    assert_allclose(DATA['tracer'], tracer[::5, :], atol=0, rtol=1e-6)
    assert_allclose(DATA['f_phi'], f_phi[::5, :], atol=0, rtol=1e-6)


def test_status_quo_cli():

    fd = pfd.FlowDiagnostics(join(SPE10_DIR, "SPE10.DATA"))
    fd.execute(time_step_id=1)

    # Read in result
    tracer = np.loadtxt(
        join(SPE10_DIR, 'SPE10.fdout/Tracer_1.csv'),
        skiprows=1, delimiter=',', dtype=np.single,
    )
    f_phi = np.loadtxt(
        join(SPE10_DIR, 'SPE10.fdout/F_Phi_1.csv'),
        skiprows=1, delimiter=',', dtype=np.single,
    )


    # Check them
    assert_allclose(DATA['tracer'], tracer[::5, :], atol=0, rtol=1e-6)
    assert_allclose(DATA['f_phi'], f_phi[::5, :], atol=0, rtol=1e-6)


@pytest.mark.script_launch_mode('subprocess')
def test_cli_main(script_runner):

    # help
    for inp in ['--help', '-h']:
        ret = script_runner.run(['pyflowdiagnostics', inp])
        assert ret.success
        assert "Run Flow Diagnostics on a reservoir simulation file." in ret.stdout

    # info
    ret = script_runner.run('pyflowdiagnostics')
    assert ret.success
    assert "Run Flow Diagnostics on a reservoir simulation file." in ret.stdout
    assert "pyflowdiagnostics v" in ret.stdout

    # report
    ret = script_runner.run(['pyflowdiagnostics', '--report'])
    assert ret.success
    # Exclude time to avoid errors.
    # Exclude pyflowdiagnostics-version (after 600), because if run locally without
    # having pyflowdiagnostics installed it will be "unknown" for the __main__ one.
    assert pyflowdiagnostics.utils.Report().__repr__()[115:600] in ret.stdout

    # version        -- VIA pyflowdiagnostics/__main__.py by calling the folder pyflowdiagnostics.
    ret = script_runner.run(['python', 'pyflowdiagnostics', '--version'])
    assert ret.success
    assert "pyflowdiagnostics v" in ret.stdout

    # Wrong function -- VIA pyflowdiagnostics/__main__.py by calling the file.
    ret = script_runner.run(
            ['python', join('pyflowdiagnostics', '__main__.py'), 'wrong'])
    assert not ret.success
    assert "error: unrecognized arguments: wrong" in ret.stderr

    # try to run
    ret = script_runner.run(
            ['pyflowdiagnostics', '-f', 'test.DATA', '-t', '1'])
    assert not ret.success
    assert "RuntimeError: Input file not found" in ret.stderr


@pytest.mark.script_launch_mode('subprocess')
def test_import_time(script_runner):
    # Relevant for responsiveness of CLI: How long does it take to import?
    cmd = ["python", "-Ximporttime", "-c", "import pyflowdiagnostics"]
    out = script_runner.run(cmd, print_result=False)
    import_time_s = float(out.stderr.split('|')[-2])/1e6
    # Currently we check t < 2.0 s (really slow, should be < 0.2 s)
    assert import_time_s < 2.0
