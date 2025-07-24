import pooch
import zipfile
import numpy as np
from os.path import join, dirname


def get_input_data(version):
    # Get data
    fname = "pyfd-data"
    out = pooch.retrieve(
        f"https://github.com/GEG-ETHZ/pyfd-data/archive/refs/tags/{version}.zip",
        "1d31e5bf605610298546cbc7800630499553502fed73a08f42885552870f29c3",
        fname=fname+".zip",
        path="data",
    )
    fdir = out.rsplit('.', 1)[0]
    with zipfile.ZipFile(out, 'r') as zip_ref:
        zip_ref.extractall(fdir)

    ecl_dir = join(fdir, f"pyfd-data-{version}", "examples", "ecl")
    spe10_dir = join(ecl_dir, "e100", "SPE10_TOPLAYER")

    return spe10_dir


def get_regression_data():
    """
    The regression-data was generated in the following way on 2025-07-24:

    --------------------------------------------------------------------------------
      Date: Thu Jul 24 14:17:05 2025 CEST

                    OS : Linux (Ubuntu 24.04)
                CPU(s) : 2
               Machine : aarch64
          Architecture : 64bit
                   RAM : 1.9 GiB
           Environment : Python
           File system : ext4

      Python 3.12.10 | packaged by conda-forge | (main, Apr 10 2025, 22:10:27)
      [GCC 13.3.0]

                 numpy : 2.2.6
                 scipy : 1.15.2
                pandas : 2.2.3
            xlsxwriter : 3.2.3
                  h5py : 3.13.0
           pymatsolver : 0.3.1
     pyflowdiagnostics : 0.1.5.dev1+gb3cc99f.d20250723
               IPython : 9.2.0
            matplotlib : 3.9.1
          python-mumps : 0.0.3
    --------------------------------------------------------------------------------

    import numpy as np
    tracer = np.loadtxt('SPE10.fdout/Tracer_1.csv',
                        skiprows=1, delimiter=',', dtype=np.single)
    f_phi = np.loadtxt('SPE10.fdout/F_Phi_1.csv',
                       skiprows=1, delimiter=',', dtype=np.single)
    np.savez_compressed('regression', f_phi=f_phi[::5, :], tracer=tracer[::5, :])
    """
    return np.load(join(dirname(__file__), 'data', 'regression.npz'))
