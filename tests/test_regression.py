import os
import pooch
import zipfile

import pyflowdiagnostics.flow_diagnostics as pfd

# Get data
FNAME = "pyfd-data"
VERSION = "2025-07-23"
OUT = pooch.retrieve(
    f"https://github.com/GEG-ETHZ/pyfd-data/archive/refs/tags/{VERSION}.zip",
    "1d31e5bf605610298546cbc7800630499553502fed73a08f42885552870f29c3",
    fname=FNAME+".zip",
    path="data",
)
FDIR = OUT.rsplit('.', 1)[0]
with zipfile.ZipFile(OUT, 'r') as zip_ref:
    zip_ref.extractall(FDIR)


def test_status_quo():

    ecl_dir = os.path.join(FDIR, f"pyfd-data-{VERSION}", "examples", "ecl")
    spe10_dir = os.path.join(ecl_dir, "e100", "SPE10_TOPLAYER")

    fd = pfd.FlowDiagnostics(os.path.join(spe10_dir, "SPE10.DATA"))
    fd.execute(time_step_id=1)

    assert 1 == 0  # TODO compare the above result to status quo!
