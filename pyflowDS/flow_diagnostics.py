# Copyright 2025 Tsubasa Onishi
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import logging
import numpy as np
import pandas as pd
import re
import scipy.sparse as sp
from enum import Enum

from pyflowDS.readers import EclReader, CmgReader
from pyflowDS.grid import Grid
from pyflowDS.well import Well
from pyflowDS.utils import get_default_solver

EPS = 1.0e-5

__all__ = ["SimulatorType", "FlowDiagnostics"]


def __dir__():
    return __all__


class SimulatorType(Enum):
    """Enum class for simulator type"""
    ECL = "ECL"
    CMG = "CMG"


class FlowDiagnostics:
    """Computes and analyzes flow diagnostics from reservoir simulation results.

    This class reads simulation outputs, calculates time-of-flight (TOF),
    tracer concentrations, flow allocation factors, and other diagnostic parameters.

    Attributes:
        input_file_path (str): Path to the simulation input file.
        output_dir (str): Directory where output files are saved.
        grid (Grid): Grid object representing the reservoir grid.
        time_step_id (Optional[int]): Current time step ID being processed.
        wells (dict[str, Well]): Dictionary of Well objects, keyed by well name.
        injectors (list[Well]): List of injector Well objects.
        producers (list[Well]): List of producer Well objects.
        binary_reader (EclReader | CmgReader): Instance of the Eclipse or CMG binary file reader.
    """


    def __init__(self, file_path: str) -> None:
        """
        Initializes the FlowDiagnostics object.

        Args:
            file_path (str): Path to the Eclipse/IX input file (.DATA/.AFI) or CMG input file (.DAT).
        """
        self.input_file_path = self._resolve_path(file_path)
        self.output_dir = self._setup_output_directory()
        self._set_simulator_specific_methods()
        self._read_static_simulator_output()
        self.time_step_id = None
        self.wells = {}
        self.injectors = []
        self.producers = []


    def execute(self, time_step_id: int) -> None:
        """Executes the flow diagnostics analysis for a given time step.

        Args:
            time_step_id (int): The time step ID to process.
        """

        logging.info(f"Working on time step {time_step_id}.")

        self.time_step_id = time_step_id
        self._read_simulator_dynamic_output()

        if self._compute_TOF_and_tracer():
            self._compute_flow_allocations()
            self._compute_other_diagnostics()
        else:
            logging.error("Failed to compute TOF and tracer concentrations.")


    # ---- Private Methods ---------------------------------------------------------------------------------------------


    def _resolve_path(self, file_path: str) -> str:
        """Resolves an absolute file path.
        Returns:
            str: Absolute path of input file path.
        """
        return os.path.abspath(os.path.join(os.getcwd(), file_path)) if not os.path.isabs(file_path) else file_path


    def _setup_output_directory(self) -> str:
        """Sets up the output directory for results.

        Returns:
            str: Path to the created output directory.
        """
        output_dir = os.path.join(os.path.dirname(self.input_file_path),
                                  f"{os.path.splitext(os.path.basename(self.input_file_path))[0]}.fdout")
        os.makedirs(output_dir, exist_ok=True)
        return output_dir


    def _detect_simulator(self) -> SimulatorType:
        """Detects the type of simulator from the file extension.

        Returns:
            SimulatorType: The detected simulator type.
        """
        _, ext = os.path.splitext(self.input_file_path)
        if ext.upper() in [".DATA", ".AFI"]:
            simulator_type = SimulatorType.ECL # e100, e300, IX, or OPM
        elif ext.upper() in [".DAT"]:
            simulator_type = SimulatorType.CMG # CMG simulators (IMEX, GEM, STARS)
        else:
            supported_ext = [".DATA", ".AFI", ".DAT"]
            raise RuntimeError(
                f"Unsupported file extension '{ext}'. Supported extensions: {', '.join(supported_ext)}."
            )
        logging.info(f"Simulator type: {simulator_type.name}.")
        return simulator_type


    def _set_simulator_specific_methods(self) -> None:
        """Sets the appropriate methods and binary reader based on simulator type."""
        simulator_type = self._detect_simulator()
        if simulator_type == SimulatorType.ECL:
            self.binary_reader = EclReader(self.input_file_path)
            self._read_grid = self._read_grid_ECL
            self._read_flux = self._read_flux_ECL
            self._read_well_completion = self._read_well_completion_ECL
        elif simulator_type == SimulatorType.CMG:
            self.binary_reader = CmgReader(self.input_file_path)
            self._read_grid = self._read_grid_CMG
            self._read_flux = self._read_flux_CMG
            self._read_well_completion = self._read_well_completion_CMG


    def _read_grid_ECL(self) -> tuple:
        """Reads static simulator output (simulator type: ECL)."""
        results_init = self.binary_reader.read_init(keys=["INTEHEAD", "PORV"])
        results_egrid = self.binary_reader.read_egrid(keys=["FILEHEAD", "NNC1", "NNC2"])
        dimens = results_init["INTEHEAD"][8:11].astype(int).tolist()
        porv = results_init["PORV"]
        dp_flag = results_egrid["FILEHEAD"][5]
        dict_NNC = {"NNC1": results_egrid["NNC1"], "NNC2": results_egrid["NNC2"]}
        return dimens, porv, dp_flag, dict_NNC


    def _read_grid_CMG(self) -> tuple:
        """Reads static simulator output (simulator type: CMG)."""

        sr3 = self.binary_reader.get_sr3()
        _, sp = self.binary_reader.get_grid_properties(keys=["GRID/BLOCKPVOL", "GRID/ICTPS1", "GRID/ICTPS2", "GRID/ICNTDR"])

        dimens = sr3.grid.cart_dims
        porv = np.zeros(sr3.grid.n_cells)  # pore volume. active cells only in CMG
        porv[~sr3.grid.cells.inactive] = sp["GRID/BLOCKPVOL"][0]

        dp_flag = 1 if sr3.grid.n_cells == 2 * len(sr3.grid.cells.volumes) else 0

        self.cellid1 = sp['GRID/ICTPS1'][0]  # upstream cells
        self.cellid2 = sp['GRID/ICTPS2'][0]  # downstream cells
        self.connection_dir = sp['GRID/ICNTDR'][0]  # connection dirs
        irregular_conx_idx = np.where(self.connection_dir > 3)[0]  # TODO: Assuming connection_dir>3 means NNC. Not fully tested.
        dict_NNC = {"NNC1": self.cellid1[irregular_conx_idx], "NNC2": self.cellid2[irregular_conx_idx]}

        return dimens, porv, dp_flag, dict_NNC


    def _read_static_simulator_output(self) -> Grid:
        """Reads static simulator output.
        Initialize grid object that manages necessary for flow diagnostics (pore volume, fluxes, connections, etc.)

        Returns:
            Grid: Grid object.
        """
        dimens, porv, dp_flag, dict_NNC = self._read_grid()
        self.grid = Grid(dimens, porv, dp_flag, dict_NNC)


    def _read_flux_from_restart_file(self, keys: list) -> dict:
        """
        Reads flux data for the given time step.

        Args:
            keys (list): List of flux keys to read (FLROILI+, FLROILJ+, FLRWATI+, FLRWATJ+, etc.).

        Returns:
            dict: Dictionary of flux data, keyed by the provided keys.

        Raises:
            IOError: If flux data cannot be read.
        """
        try:
            # Read fluxes at reservoir conditions
            results_rst = self.binary_reader.read_rst(keys, self.time_step_id)

            # If all arrays are empty, try surface conditions
            if all(arr.size == 0 for arr in results_rst.values()):

                # Generate alternative surface flux and inverse formation volume factor (FVF) keys
                keys_flo = [key.replace("FLR", "FLO") for key in keys]
                keys_fvf = self.grid.get_inv_fvf_keys()

                logging.info(f"Fluxes at reservoir condition: {keys} not found. Computing using fluxes at surface condition and FVF.")

                # Read surface fluxes and formation volume factors
                results = self.binary_reader.read_rst(keys_flo + keys_fvf, self.time_step_id)

                # Extract valid keys before computing reservoir condition fluxes
                d_fluxes = {key: results[key] for key in keys_flo if key in results}
                d_inv_fvf = {key: results[key] for key in keys_fvf if key in results}

                if all(arr.size == 0 for arr in d_fluxes.values()):
                    raise RuntimeError("Surface fluxes are not found. Check RPTRST.")

                return self.grid.compute_flux_reservoir_cond(d_fluxes, d_inv_fvf)

            # Return the successfully read reservoir condition fluxes
            return {key: results_rst[key] for key in keys if key in results_rst}

        except Exception as e:
            raise IOError(f"Failed to read fluxes (keys: {keys}): {e}")


    def _read_flux_ECL(self) -> tuple[dict, dict]:
        d_fluxes = self._read_flux_from_restart_file(self.grid.get_flux_keys())
        d_NNC_fluxes = self._read_flux_from_restart_file(self.grid.get_NNC_flux_keys()) if self.grid.NNC else None
        return d_fluxes, d_NNC_fluxes


    def _read_flux_CMG(self) -> tuple[dict, dict]:
        """
        Read flux outputs from sr3 file, then convert them into Eclipse style format.

        Assumptions based on some experiments (no documentation found in the CMG manuals):

        - With the `FLUXCON` keyword, fluxes for all phases (`FLUXCONW`, `FLUXCONO`, `FLUXCONG`) are always generated,
          even in single/two-phase flow cases.
        - Flux values are in **reservoir conditions**.
        - `connection_dir > 3` means **NNCs** (1: I-dir, 2: J-dir, and 3: K-dir).

        Returns:
            tuple[dict, dict]: A tuple containing:

            - **d_fluxes**: Standard flux dictionary.
            - **d_NNC_fluxes**: NNC flux dictionary.
        """

        sp_ind, sp = self.binary_reader.get_grid_properties(keys=["FLUXCONW", "FLUXCONO", "FLUXCONG"])
        self.sp_ind = np.array(sp_ind)

        if isinstance(sp["FLUXCONW"], list) and not sp["FLUXCONW"]:
            raise RuntimeError(f"Failed to read fluxes. Ensure FLUXCON keyword is set in OUTSRF.")
        try:
            FLUXCONW = sp["FLUXCONW"][self.time_step_id]
            FLUXCONO = sp["FLUXCONO"][self.time_step_id]
            FLUXCONG = sp["FLUXCONG"][self.time_step_id]
        except Exception as e:
            raise RuntimeError(f"Failed to read fluxes: {e}. Check if fluxes are reported at time step: {self.time_step_id}")

        # Identify indices for different connection types
        idx_dirs = {
            "I": np.where(self.connection_dir == 1)[0],
            "J": np.where(self.connection_dir == 2)[0],
            "K": np.where(self.connection_dir == 3)[0],
            "N": np.where(self.connection_dir > 3)[0],  # "N" for NNCs
        }

        # Standard connection cell IDs
        cellids = {
            "I": (self.cellid1[idx_dirs["I"]], self.cellid2[idx_dirs["I"]]),
            "J": (self.cellid1[idx_dirs["J"]], self.cellid2[idx_dirs["J"]]),
            "K": (self.cellid1[idx_dirs["K"]], self.cellid2[idx_dirs["K"]]),
        }

        # NNC connection cell IDs
        nnc1, nnc2 = self.cellid1[idx_dirs["N"]], self.cellid2[idx_dirs["N"]]

        # Initialize flux dictionaries
        d_fluxes, d_NNC_fluxes = {}, {}

        # Standard flux processing
        d_FLUXCON = {"OIL": FLUXCONO, "WAT": FLUXCONW, "GAS": FLUXCONG}

        for key in self.grid.get_flux_keys():
            phase = key[3:6]  # Extract "OIL", "WAT", or "GAS"
            direction = key[6]  # Extract "I", "J", or "K"
            if phase not in d_FLUXCON or direction not in cellids:
                logging.debug(f"Skipping invalid phase or direction. phase: {phase}, dir: {direction}")
                continue  # Skip if not a valid phase or directions

            FLUXCON = d_FLUXCON[phase]
            idx_dir = idx_dirs[direction]
            cellid1, _ = cellids[direction]

            q_tmp = np.zeros(self.grid.nn)
            q_tmp[cellid1 - 1] = -FLUXCON[idx_dir]  # Minus sign for Eclipse format
            d_fluxes[key] = q_tmp[self.grid.actnum_bool]

        #
        # ... NNCs
        #

        ecl_NNC_flux_keys = self.grid.get_NNC_flux_keys()
        if idx_dirs["N"].size:
            for key in self._NNC_flux_keys:
                phase = key[3:6]
                if phase in d_FLUXCON:
                    d_NNC_fluxes[key] = -d_FLUXCON[phase][idx_dirs["N"]]
        else:
            d_NNC_fluxes = None

        return d_fluxes, d_NNC_fluxes


    def _read_well_completion_ECL(self) -> None:
        """Reads well completions from restart file."""
        results_rst = self.binary_reader.read_rst(keys=["INTEHEAD", "ZWEL", "IWEL", "ICON"], tstep_id=self.time_step_id)

        NWELLS, NCWMAX, NICONZ = results_rst["INTEHEAD"][16], results_rst["INTEHEAD"][17], results_rst["INTEHEAD"][32]
        ZWEL, IWEL, ICON = results_rst["ZWEL"], results_rst["IWEL"], results_rst["ICON"]
        IWEL = IWEL.reshape((-1, NWELLS), order="F")
        ICON = ICON.reshape((NICONZ, NCWMAX, NWELLS), order="F")

        well_names = [''.join(row).strip() for row in ZWEL if ''.join(row).strip()]
        self.wells = {name: Well(name=name, type_id=IWEL[6, i]) for i, name in enumerate(well_names)}

        for i, name in enumerate(well_names):
            for completion in ICON[:, :, i].T:
                if completion[0] == 0:
                    break
                I, J, K = completion[1:4]
                well = self.wells[name]
                well.add_completion(I=I, J=J, K=K, stat=completion[5])
                well.completions[-1].set_ijk(self.grid.ijk_from_I_J_K(I, J, K))
                well.completions[-1].set_flow_rate(self.grid.compute_outflow(I, J, K))

        # set well status (OPEN/SHUT) according to completion status
        for name in well_names: self.wells[name].set_status()


    def _read_well_completion_CMG(self) -> None:
        """
        Reads well completions from `sr3` file.

        Assumptions (no documentation found in the CMG manuals):

        **Well Type:**

        - `WELLOPMO > 0`: Injector
        - `WELLOPMO < 0`: Producer

        **Well Status:**

        - `WELLSTATE = 0`: OPEN
        - `WELLSTATE = 1`: SHUT
        """

        sr3 = self.binary_reader.get_sr3()

        well_names = np.char.decode(sr3.data['TimeSeries/WELLS/Origins'], 'utf-8')
        well_time_series = self.binary_reader.get_time_series()

        t_well_time_series = well_time_series[well_names[0]].index.values
        is_init_step_output = False if t_well_time_series[0] > 0 else True

        # initialize well objects
        self.wells = {}
        for well_name in well_names:
            df = well_time_series[well_name]
            try:
                WELLOPMO = df['WELLOPMO'].values
            except:
                ValueError(f"Required key: 'WELLOPMO' is not found.")
            well_type = 0 # unknown
            if not is_init_step_output:
                if WELLOPMO[self.time_step_id] > 0:
                    well_type = 5 # injector
                elif WELLOPMO[self.time_step_id] < 0:
                    well_type = 1 # producer
            self.wells[well_name] = Well(well_name, well_type)

        # add completions for each well
        pattern = r'(\w+)\{(\d+,\d+,\d+)\}'
        try:
            well_completions = sr3.data['TimeSeries/LAYERS/Origins']
        except:
            raise ValueError(f"Required output 'TimeSeries/LAYERS/Origins' is not found.")

        for cmpl_info in well_completions:
            match = re.match(pattern, cmpl_info.decode('utf-8'))
            if match:
                well_name = match.group(1)
                well = self.wells[well_name]
                I, J, K = [int(num) for num in str(f"[{match.group(2)}]").strip('[]').split(',')]
                df = well_time_series[well_name]
                status_arr = df["WELLSTATE"].values
                if not is_init_step_output:
                    status_arr = np.insert(status_arr,0,0)
                well.add_completion(I=I, J=J, K=K,
                                    stat = 0 if status_arr[self.time_step_id] == 1 else 1)
                well.completions[-1].set_ijk(self.grid.ijk_from_I_J_K(I, J, K))
                well.completions[-1].set_flow_rate(self.grid.compute_outflow(I, J, K))


    def _read_simulator_dynamic_output(self) -> None:
        """Reads dynamic simulator output including fluxes and well completions."""
        logging.info(f"Reading dynamic simulation outputs.")

        # Read fluxes
        d_fluxes, d_NNC_fluxes = self._read_flux()
        self.grid.compute_total_fluxes(d_fluxes, d_NNC_fluxes)

        # Read well and completion data
        self._read_well_completion()


    def _solve_TOF_tracer(self, wells: list[Well]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Solves the Time-of-Flight (TOF) and tracer equations for the given source wells.

         This method constructs and solves a sparse linear system to determine the TOF
         and tracer concentrations in each grid cell.  It handles both injector and
         producer wells.

         Args:
             wells (list[Well]): A list of `Well` objects representing the source wells
                 (either injectors or producers).

         Returns:
             tuple[np.ndarray, np.ndarray, np.ndarray]: A tuple containing:
                 - tof (np.ndarray): A 1D NumPy array of Time-of-Flight values for each grid cell.
                 - tracer (np.ndarray): A 2D NumPy array of tracer concentrations. Each column
                   corresponds to a source well, and each row corresponds to a grid cell.
                 - partition (np.ndarray): A 1D NumPy array representing the partition of each
                   grid cell based on tracer concentration.
         """

        nn = self.grid.nn  # Total number of grid cells
        nact = self.grid.num_active_cells  # Number of active cells
        conx = self.grid.get_connections()  # Grid cell connections
        total_flux_flattened = self.grid.get_total_flux_flattened()  # Flattened flux values

        # --- Construct RHS (b) ---
        rhs = np.zeros((nn, len(wells) + 1))
        rhs[:, 0] = self.grid.porv  # Assign pore volume to the first column

        # Assign fluxes at source cells to the 2:num_wells columns for tracer eqs rhs.
        for i, well in enumerate(wells):
            for cmpl in well.completions:
                if cmpl.status == "OPEN":
                    rhs[cmpl.IJK - 1, i + 1] = cmpl.flow_rate

        # Aggregate total fluxes at well cells
        inflow_source = np.sum(rhs[:, 1:], axis=1)[self.grid.actnum_bool]

        # --- Construct Flow Matrix (A) ---

        # Reverse fluxes if dealing with producers
        if wells[0].type == "PRD":
            inflow_source, total_flux_flattened = -inflow_source, -total_flux_flattened

        inflow = np.maximum(total_flux_flattened, 0)
        outflow = np.minimum(total_flux_flattened, 0)

        # initialize total inflow w/o inflow from source(s)
        inflow_total = np.zeros(nact)
        np.add.at(inflow_total, conx[:, 1] - 1, inflow)
        np.add.at(inflow_total, conx[:, 0] - 1, -outflow)

        d = inflow_total + inflow_source  # Total inflow (diagonal terms)

        # Flux sparse matrix representation
        F = sp.csr_matrix((
            np.hstack([inflow, -outflow]),
            (np.hstack([conx[:, 1] - 1, conx[:, 0] - 1]),
             np.hstack([conx[:, 0] - 1, conx[:, 1] - 1]))
        ), shape=(nact, nact))

        # Modify diagonal elements
        F = -F + sp.diags(d, 0, shape=(nact, nact))

        # filter out cells without inflows (avoid singular matrix)
        active_cells_inflow = np.abs(F.diagonal()) > EPS

        # Apply filters (actnum + inflow flag)
        b = rhs[self.grid.actnum_bool, :][active_cells_inflow, :]
        A = F[active_cells_inflow][:, active_cells_inflow]

        # solve Ax=b
        solve = get_default_solver()
        Ainv = solve(A)
        x = Ainv * b

        # --- Assign solutions to full arrays ---
        tof = np.full(nn, np.nan)
        tracer = np.full((nn, len(wells)), np.nan)

        # Map solved values back to full grid
        active_cell_indices = np.where(self.grid.actnum_bool)[0][active_cells_inflow]
        tof[active_cell_indices] = x[:, 0]
        tracer[active_cell_indices, :] = x[:, 1:]

        # Compute partitioning based on tracer concentration
        partition = self.compute_partition(tracer)

        return tof, tracer, partition


    def _compute_TOF_and_tracer(self) -> bool:
        """Computes Time-of-Flight (TOF) and tracer concentrations.

        This method calculates TOF and tracer distributions for both injectors and
        producers.  It calls the `_solve_TOF_tracer` method for each well type.

        Returns:
            bool: True if the TOF and tracer computations were successful, False otherwise.
        """
        logging.info("Computing TOF and tracer concentrations.")

        if not self.wells:
            logging.warning("No wells found. Skipping TOF computation.")
            return False

        self.injectors = [well for well in self.wells.values() if well.type == "INJ" and well.status == "OPEN"]
        self.producers = [well for well in self.wells.values() if well.type == "PRD" and well.status == "OPEN"]

        self.tofI, self.CI, self.partI = self._solve_TOF_tracer(self.injectors) if self.injectors else (None, None, None)
        self.tofP, self.CP, self.partP = self._solve_TOF_tracer(self.producers) if self.producers else (None, None, None)

        self.well_pair_ids = self.compute_well_pair_ids(self.partI, self.partP)

        return self._write_grid_flow_diagnostics()


    def _compute_other_diagnostics(self) -> None:
        """Computes additional flow diagnostics (F-Phi plots, sweep efficiency, etc.).

        This method calculates and saves additional flow diagnostics based on computed
        TOF and tracer results. Handles both single and dual porosity cases.
        """
        if not self.injectors or not self.producers:
            logging.debug(
                "Skipping computation of other flow diagnostics (F-Phi plots, sweep efficiency) "
                "due to missing injectors or producers (total TOF is required)."
            )
            return

        logging.info("Computing additional flow diagnostics (F-Phi plots, sweep efficiency).")

        # Replace NaN values in TOF arrays with their maximum valid value
        tof_inj_no_nan = np.where(np.isnan(self.tofI), np.nanmax(self.tofI, initial=0), self.tofI)
        tof_prod_no_nan = np.where(np.isnan(self.tofP), np.nanmax(self.tofP, initial=0), self.tofP)

        if self.grid.dual_poro:
            # --- Dual Porosity Case ---
            nM = len(tof_inj_no_nan) // 2  # Half for matrix, half for fracture

            # Split TOF into matrix and fracture domains
            tof_inj_matrix, tof_inj_fracture = tof_inj_no_nan[:nM], tof_inj_no_nan[nM:]
            tof_prod_matrix, tof_prod_fracture = tof_prod_no_nan[:nM], tof_prod_no_nan[nM:]

            # Split active cell and pore volume arrays
            actnum_matrix, actnum_fracture = self.grid.actnum_bool[:nM], self.grid.actnum_bool[nM:]
            porv_matrix, porv_fracture = self.grid.porv[:nM], self.grid.porv[nM:]

            # Extract valid TOF values for active cells
            tof_valid_matrix = np.column_stack([tof_inj_matrix[actnum_matrix], tof_prod_matrix[actnum_matrix]])
            tof_valid_fracture = np.column_stack(
                [tof_inj_fracture[actnum_fracture], tof_prod_fracture[actnum_fracture]])

            # Compute F-Phi plots
            self.FM, self.PhiM = self.compute_F_and_Phi(porv_matrix[actnum_matrix], tof_valid_matrix)
            self.FF, self.PhiF = self.compute_F_and_Phi(porv_fracture[actnum_fracture], tof_valid_fracture)

            # Compute sweep efficiency
            self.EvM, self.tDM = self.compute_sweep(self.FM, self.PhiM)
            self.EvF, self.tDF = self.compute_sweep(self.FF, self.PhiF)

            # Compute tracer concentration
            self.CM = 1 - np.diff(self.EvM) / (np.diff(self.tDM) + EPS)
            self.CF = 1 - np.diff(self.EvF) / (np.diff(self.tDF) + EPS)

        else:
            # --- Single Porosity Case ---
            tof_valid = np.column_stack([tof_inj_no_nan[self.grid.actnum_bool], tof_prod_no_nan[self.grid.actnum_bool]])

            # Compute F-Phi plots
            self.F, self.Phi = self.compute_F_and_Phi(self.grid.porv[self.grid.actnum_bool], tof_valid)

            # Compute sweep efficiency
            self.Ev, self.tD = self.compute_sweep(self.F, self.Phi)

            # Compute tracer concentration
            self.C = 1 - np.diff(self.Ev) / (np.diff(self.tD) + EPS)

        # Write results to file
        self._write_other_flow_diagnostics()


    def _compute_flow_allocations(self) -> None:
        """Computes flow allocation matrices for injectors and producers.

        This method calculates and stores flow allocation factors, which indicate
        how much each injector contributes to each producer (and vice-versa).
        """
        if not self.injectors or not self.producers:
            logging.debug("Skipping computation of allocation factors due to missing injectors or producers.")
            return

        injector_names = [well.name for well in self.injectors]
        producer_names = [well.name for well in self.producers]

        FlowAllocI = self._compute_flow_allocation(self.injectors, self.CP, producer_names)
        FlowAllocP = self._compute_flow_allocation(self.producers, self.CI, injector_names)

        self._write_allocation_factors(FlowAllocI, FlowAllocP)


    def _compute_flow_allocation(self, wells, C_matrix, target_names):
        """Helper function to compute flow allocation matrices.

        Args:
            wells (list[Well]): List of Well objects (injectors or producers).
            C_matrix (np.ndarray): Tracer concentration matrix.
            target_names (list[str]): Names of the target wells.

        Returns:
            pd.DataFrame: DataFrame containing the flow allocation matrix.
        """
        FlowAlloc = np.zeros((len(wells), len(target_names)))
        for i, well in enumerate(wells):
            for j in range(len(target_names)):
                for cmpl in well.completions:
                    if cmpl.status == "OPEN":
                        FlowAlloc[i, j] += C_matrix[cmpl.IJK - 1, j]
            FlowAlloc[i, :] /= np.sum(FlowAlloc[i, :]) if np.sum(np.abs(FlowAlloc[i, :])) > 0 else 1
        return pd.DataFrame(FlowAlloc, columns=target_names, index=[well.name for well in wells])


    def _write_allocation_factors(self, df_inj, df_prd) -> None:
        """Saves flow allocation factors to an Excel file.

        Args:
            df_inj (pd.DataFrame): DataFrame of injector flow allocation.
            df_prd (pd.DataFrame): DataFrame of producer flow allocation.
        """
        file_path = os.path.join(self.output_dir, "Allocation_Factor.xlsx")
        with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
            df_inj.to_excel(writer, sheet_name="Injector Flow Allocation")
            df_prd.to_excel(writer, sheet_name="Producer Flow Allocation")
        logging.info(f"Flow allocation factors saved to {file_path}")


    def _write_grid_flow_diagnostics(self) -> bool:
        """Writes flow diagnostics results to a GRDECL file.

        Saves computed TOF (Time-of-Flight) and partitioning data to a GRDECL file for visualization in Petrel.
        Handles both single and dual porosity cases and replaces NaN values appropriately.

        Returns:
            bool: True if writing to the GRDECL file was successful, False otherwise.
        """
        file_path = os.path.join(self.output_dir, f"GridFlowDiagnostics_{self.time_step_id}.GRDECL")

        # --- Prepare Data for Writing ---
        if self.grid.dual_poro:
            num_matrix_cells = len(self.tofI) // 2 if self.tofI is not None else len(self.tofP) // 2
            data_labels = {
                "TOFIM": self.tofI[:num_matrix_cells] if self.tofI is not None else None,
                "TOFIF": self.tofI[num_matrix_cells:] if self.tofI is not None else None,
                "PARTIM": self.partI[:num_matrix_cells] if self.partI is not None else None,
                "PARTIF": self.partI[num_matrix_cells:] if self.partI is not None else None,
                "TOFPM": self.tofP[:num_matrix_cells] if self.tofP is not None else None,
                "TOFPF": self.tofP[num_matrix_cells:] if self.tofP is not None else None,
                "PARTPM": self.partP[:num_matrix_cells] if self.partP is not None else None,
                "PARTPF": self.partP[num_matrix_cells:] if self.partP is not None else None,
                "WELLPAIRM": self.well_pair_ids[:num_matrix_cells] if self.well_pair_ids is not None else None,
                "WELLPAIRF": self.well_pair_ids[num_matrix_cells:] if self.well_pair_ids is not None else None,
            }
        else:
            data_labels = {
                "TOFI": self.tofI, "PARTI": self.partI,
                "TOFP": self.tofP, "PARTP": self.partP,
                "WELLPAIR": self.well_pair_ids
            }

        # Remove None values
        data_labels = {key: val for key, val in data_labels.items() if val is not None}

        # If no valid data, log a warning and exit
        if not data_labels:
            logging.warning("Skipping _write_grid_flow_diagnostics: No valid TOF or partitioning data to write.")
            return False

        # --- Replace NaNs and Handle Data Formatting ---
        for label, data in data_labels.items():
            if np.all(np.isnan(data)):  # If all values are NaN, replace with 0
                data_labels[label] = np.zeros_like(data)
                logging.debug(f"All values in {label} are NaN, replacing with zeros.")
            elif "TOF" in label:
                data_labels[label] = np.where(np.isnan(data), np.nanmax(data, initial=0),
                                              data)  # Replace NaNs with max valid value
            else:
                data_labels[label] = np.where(np.isnan(data), -1, data)  # Replace NaNs with -1 for categorical/int data

        # --- Write Data to GRDECL File ---
        try:
            with open(file_path, "w") as fid:
                for label, data in data_labels.items():
                    fid.write(f"{label}\n")
                    np.savetxt(fid, data, fmt="%e" if "TOF" in label else "%3d")
                    fid.write(f"/\n")

            logging.info(f"Flow diagnostics results saved to: {file_path}")
            return True

        except Exception as e:
            logging.error(f"Error writing to {file_path}: {e}")
            return False


    def _write_other_flow_diagnostics(self) -> None:
        """Generates and saves flow diagnostics plots (F-Phi, tracer concentration)
        and writes outputs into csv files."""

        if self.grid.dual_poro:

            df_FPhi_fracture = pd.DataFrame({'Storage Capacity': self.PhiF, 'Flow Capacity': self.FF})
            df_FPhi_fracture.to_csv(os.path.join(self.output_dir, f"F_Phi_Fracture_{self.time_step_id}.csv"), index=False)

            df_FPhi_matrix = pd.DataFrame({'Storage Capacity': self.PhiM, 'Flow Capacity': self.FM})
            df_FPhi_matrix.to_csv(os.path.join(self.output_dir, f"F_Phi_Matrix_{self.time_step_id}.csv"), index=False)

            df_tracer_fracture = pd.DataFrame({'Time PVI': self.tDF[:-1], 'Tracer Concentration': self.CF})
            df_tracer_fracture.to_csv(os.path.join(self.output_dir, f"Tracer_Fracture_{self.time_step_id}.csv"), index=False)

            df_tracer_matrix = pd.DataFrame({'Time PVI': self.tDM[:-1], 'Tracer Concentration': self.CM})
            df_tracer_matrix.to_csv(os.path.join(self.output_dir, f"Tracer_Matrix_{self.time_step_id}.csv"), index=False)

        else:

            df_FPhi = pd.DataFrame({'Storage Capacity': self.Phi, 'Flow Capacity': self.F})
            df_FPhi.to_csv(os.path.join(self.output_dir, f"F_Phi_{self.time_step_id}.csv"), index=False)

            df_tracer = pd.DataFrame({'Time PVI': self.tD[:-1], 'Tracer Concentration': self.C})
            df_tracer.to_csv(os.path.join(self.output_dir, f"Tracer_{self.time_step_id}.csv"), index=False)


    # ---- Static Methods ---------------------------------------------------------------------------------------------


    @staticmethod
    def compute_partition(C):
        """Computes the partition of grid cells based on tracer concentrations.

        This static method determines which source well (injector, or producer with a reversed flux field)
         has the highest tracer concentration in each grid cell.

        Args:
            C (np.ndarray): A 2D NumPy array of tracer concentrations.  The shape should
                be (number of grid cells, number of injectors).

        Returns:
            np.ndarray: A 1D NumPy array representing the partition. Each element
                corresponds to a grid cell and indicates the index (1-based) of the
                source well with the maximum absolute tracer concentration.  NaN values
                are assigned where the maximum concentration is 0 or NaN.
        """

        # Compute max absolute value along columns (axis=1)
        val = np.max(np.abs(C), axis=1)

        # Get index (1-based) of the maximum value per row
        partition = np.argmax(np.abs(C), axis=1) + 1.  # 0-based, add 1

        # Set partI to NaN where val == 0 or val is NaN_
        partition[(val == 0) | np.isnan(val)] = np.nan

        return partition


    @staticmethod
    def compute_well_pair_ids(partI, partP):
        """Computes the partition of grid cells based on tracer concentrations.

        This static method determines well pair ids at each cell, based on injector
        and producer partitions.

        Args:
            partI (np.ndarray): A 2D NumPy array of partition ids (injectors).
            partP (np.ndarray): A 2D NumPy array of partition ids (producers).

        Returns:
            np.ndarray: A 1D NumPy array representing the well pair ids.
        """

        if partI is None or partP is None:
            return None

        # Stack injectors and producers to create well pairs
        well_pairs = np.column_stack((partI, partP))

        # Remove rows where either injector or producer is NaN
        valid_mask = ~np.isnan(well_pairs).any(axis=1)
        unique_pairs, inverse_indices = np.unique(well_pairs[valid_mask], axis=0, return_inverse=True)

        # Create well pair IDs: start from 1
        well_pair_ids = np.full(well_pairs.shape[0], np.nan)  # Initialize with NaN
        well_pair_ids[valid_mask] = inverse_indices + 1  # Assign unique IDs (1, 2, 3...)

        return well_pair_ids


    @staticmethod
    def compute_F_and_Phi(pv: np.ndarray, tof: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Computes the flow-capacity/storage-capacity diagram (F, Phi).

        Args:
            pv (np.ndarray): A 1D NumPy array of pore volumes for each grid cell.
            tof (np.ndarray): A 2D NumPy array of time-of-flight values from injector and
                producer, per cell.  Should have two columns.

        Returns:
            tuple[np.ndarray, np.ndarray]: A tuple containing:
                - F (np.ndarray): Flow capacity (cumulative flux).
                - Phi (np.ndarray): Storage capacity (cumulative pore volume).
        """

        assert tof.shape[1] == 2, "Tof input must have two columns."

        # Compute total travel time for each cell
        t = np.sum(tof, axis=1)

        # Sort cells based on total travel time
        order = np.argsort(t)
        ts_sorted = t[order]

        # Reorder volumes according to travel time
        v_sorted = pv[order]

        # Compute cumulative storage capacity (Phi)
        Phi = np.cumsum(v_sorted)
        total_volume = Phi[-1]  # Total volume of the region
        Phi = np.concatenate(([0], Phi / total_volume))  # Normalize Phi

        # Compute flux per cell (assuming incompressible flow)
        flux = v_sorted / (ts_sorted + EPS)  # Avoid division by zero

        # Compute cumulative flow capacity (F)
        F = np.cumsum(flux)
        total_flux = F[-1]  # Total flux computed
        F = np.concatenate(([0], F / total_flux))  # Normalize F

        return F, Phi


    @staticmethod
    def compute_sweep(F: np.ndarray, Phi: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Computes sweep efficiency versus dimensionless time (PVI).

        Args:
            F (np.ndarray): Flow capacity.
            Phi (np.ndarray): Storage capacity.

        Returns:
            tuple[np.ndarray, np.ndarray]: A tuple containing:
                - Ev (np.ndarray): Sweep efficiency.
                - tD (np.ndarray): Dimensionless time (PVI).
        """

        # Ensure F and Phi are numpy arrays
        F = np.asarray(F)
        Phi = np.asarray(Phi)

        # Remove any null segments to avoid division by zero
        hit = np.ones_like(F, dtype=bool)
        hit[1:] = F[:-1] != F[1:]

        F = F[hit]
        Phi = Phi[hit]

        # Compute dimensionless time (avoid division by zero)
        tD = np.zeros_like(F)
        tD[1:] = (Phi[1:] - Phi[:-1]) / (F[1:] - F[:-1] + EPS)

        # Compute sweep efficiency
        Ev = Phi + (1 - F) * tD

        return Ev, tD


    @staticmethod
    def compute_Lorenz(F, Phi):
        """Computes the Lorenz coefficient, a measure of heterogeneity.

        Args:
            F (np.ndarray): Flow capacity.
            Phi (np.ndarray): Storage capacity.

        Returns:
            float: The Lorenz coefficient.
        """
        v = np.diff(Phi)
        Lc = 2 * (np.sum((F[:-1] + F[1:]) / 2 * v) - 0.5)

        return Lc





