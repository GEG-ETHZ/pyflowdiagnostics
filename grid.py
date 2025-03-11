import numpy as np
import logging

NUM_MAX_DIMENS = 3
NUM_MAX_PHASES = 3

class Grid:
    """Manages grid properties and fluxes.

    Stores grid dimensions, pore volume, active cell information,
    and handles flux calculations. Supports dual porosity and
    non-neighboring connections (NNCs).

    Attributes:
        nx (int): Number of grid cells in the x-direction.
        ny (int): Number of grid cells in the y-direction.
        nz (int): Number of grid cells in the z-direction.
        nn (int): Total number of grid cells.
        num_max_dims (int): Maximum number of dimensions (typically 3).
        num_max_phases (int): Maximum number of fluid phases (typically 3).
        single_layer (bool): True if the grid has only one layer (nz == 1 or nz==2 in DP).
        porv (np.ndarray): Pore volume array.
        actnum (np.ndarray): Active cell mask (1 for active cells, 0 otherwise).
        actnum_bool (np.ndarray): Boolean array indicating active cells.
        num_active_cells (int): Number of active grid cells.
        dual_poro (bool): True if dual porosity is enabled.
        NNC (bool): True if non-neighboring connections (NNCs) are enabled.
        _flux_keys (list): List of flux keys for standard connections.
        _NNC_flux_keys (list): List of flux keys for NNC connections.
        _q_xyz (np.ndarray): Array of phase fluxes in all directions.
        _Qx, _Qy, _Qz (np.ndarray): Flux arrays in x, y, and z directions.
        _conx (np.ndarray): Connection matrix.
        _valid_conx_idx (np.ndarray): Boolean array indicating valid connections.
        _Qxyz_flattened (np.ndarray): Flattened array of all valid fluxes.
    """


    def __init__(self, dimens: tuple, porv: np.ndarray, dp_flag: int, dict_NNC: dict) -> None:
        """Initializes the Grid object.

        Args:
            dimens (tuple): Grid dimensions (nx, ny, nz).
            porv (np.ndarray): Pore volume array.
            dp_flag (int): Dual porosity flag (0 for single porosity, 1 or 2 for dual porosity).
            dict_NNC (dict): Dictionary containing NNC data (NNC1, NNC2).
        """

        # Grid properties
        self.nx, self.ny, self.nz = dimens
        self.nn = self.nx * self.ny * self.nz
        self.num_max_dims = NUM_MAX_DIMENS
        self.num_max_phases = NUM_MAX_PHASES
        self.single_layer = self.nz == 1
        self.porv = porv
        self.actnum = (porv > 0).astype(int)
        self.actnum_bool = (porv > 0).astype(bool)
        self.num_active_cells = np.sum(self.actnum)

        self._set_dual_poro(dp_flag)
        self._set_NNC(dict_NNC)
        self._compute_connections()
        self._initialize_flux_keys()
        self._initialize_fvf_keys()


    def get_connections(self):
        """Returns the connection matrix.

        Returns:
            np.ndarray: The connection matrix.
        """
        return self._conx


    def get_flux_keys(self):
        """Returns the flux keys for standard connections.

        Returns:
            list: List of flux keys.
        """
        return self._flux_keys


    def get_NNC_flux_keys(self):
        """Returns the flux keys for NNC connections, if applicable.

        Returns:
            list or None: List of NNC flux keys, or None if NNCs are not enabled.
        """
        return self._NNC_flux_keys if self.NNC else None



    def get_total_flux_flattened(self):
        """Returns the total flux.

        Returns:
            np.ndarray: The flattened total flux.
        """
        return self._Qxyz_flattened


    def get_inv_fvf_keys(self):
        """Returns the inverse FVF keys.

        Returns:
            list: List of inverse FVF keys.
        """
        return self._inv_fvf_keys


    def ijk_from_I_J_K(self, I: int, J: int, K: int) -> int:
        """Calculates the ijk index from I, J, K indices.

        Args:
            I (int): I-index of the grid cell.
            J (int): J-index of the grid cell.
            K (int): K-index of the grid cell.

        Returns:
            int: ijk index of the grid cell.
        """
        return I + (J-1) * self.nx + (K-1) * self.nx * self.ny


    def compute_flux_reservoir_cond(self, d_fluxes: dict, d_inv_fvf: dict) -> dict:
        """Computes fluxes in reservoir condition using fluxes in surface condition and formation volume factors.

        Args:
            d_fluxes (dict): Dictionary of flux data for standard connections.
            d_inv_fvf (dict): Dictionary of inverse formation volume factors

        Returns:
            dict: fluxes in reservoir condition.
        """

        d_flr = {}
        nx, ny, nz, nn = self.nx, self.ny, self.nz, self.nn
        actnum_bool = self.actnum_bool

        # Phase-FVF mapping
        phase_fvf_map = {
            'FLOOIL': '1OVERBO',
            'FLOWAT': '1OVERBW',
            'FLOGAS': '1OVERBG'
        }

        is_nnc_flux = any("N+" in key for key in d_fluxes)

        for key, flo_arr in d_fluxes.items():

            key_res_cond = key.replace("FLO", "FLR")

            if flo_arr.size == 0:
                d_flr[key_res_cond] = flo_arr  # Preserve empty arrays
                continue

            # Determine phase FVF key
            fvf_key = next((fvf for phase, fvf in phase_fvf_map.items() if phase in key), None)
            if fvf_key is None:
                raise ValueError(f"Could not determine FVF key for flux key: {key}")

            inv_fvf_array = d_inv_fvf.get(fvf_key)
            if inv_fvf_array is None or inv_fvf_array.size == 0:
                raise ValueError(f"Flux array {key} is non-empty, but corresponding FVF {fvf_key} is empty.")

            if is_nnc_flux:

                inv_fvf_tmp = np.zeros(nn)
                inv_fvf_tmp[actnum_bool] = inv_fvf_array
                inv_fvf_down = inv_fvf_tmp[self.NNC1 - 1]
                inv_fvf_up = inv_fvf_tmp[self.NNC2 - 1]
                inv_fvf_selected = np.where(flo_arr > 0, inv_fvf_down, inv_fvf_up)
                d_flr[key_res_cond] = flo_arr / np.maximum(inv_fvf_selected, 1e-10)  # Avoid division by zero

            else:

                # Reshape data to 3D grid format
                flux_tmp, inv_fvf_tmp = np.zeros(nn), np.zeros(nn)
                flux_tmp[actnum_bool], inv_fvf_tmp[actnum_bool] = flo_arr, inv_fvf_array

                flo_3D = flux_tmp.reshape(nx, ny, nz, order="F")
                inv_fvf_3D = inv_fvf_tmp.reshape(nx, ny, nz, order="F")

                # Determine upstream FVF based on flow direction
                upstream_inv_fvf = np.zeros_like(inv_fvf_3D)
                if 'I+' in key:
                    upstream_inv_fvf[:-1, :, :] = np.where(flo_3D[:-1, :, :] > 0, inv_fvf_3D[:-1, :, :], inv_fvf_3D[1:, :, :])
                elif 'J+' in key:
                    upstream_inv_fvf[:, :-1, :] = np.where(flo_3D[:, :-1, :] > 0, inv_fvf_3D[:, :-1, :], inv_fvf_3D[:, 1:, :])
                elif 'K+' in key:
                    upstream_inv_fvf[:, :, :-1] = np.where(flo_3D[:, :, :-1] > 0, inv_fvf_3D[:, :, :-1], inv_fvf_3D[:, :, 1:])
                else:
                    raise ValueError(f"Unexpected flux key: {key}")

                # Convert to reservoir condition (avoiding division by zero)
                flr_3D = flo_3D / np.maximum(upstream_inv_fvf, 1e-10)
                flr_1D = flr_3D.ravel(order="F")

                # Store only active cell values
                d_flr[key_res_cond] = flr_1D[actnum_bool]

        return d_flr


    def compute_total_fluxes(self, d_fluxes: dict, d_NNC_fluxes: dict = None) -> None:
        """Computes and stores total fluxes, including NNC fluxes.

        Args:
            d_fluxes (dict): Dictionary of flux data for reservoir connections.
            d_NNC_fluxes (dict, optional): Dictionary of flux data for NNC connections. Defaults to None.
        """
        logging.info("Computing total fluxes using phase fluxes.")

        nx, ny, nz = self.nx, self.ny, self.nz
        self._q_xyz = np.zeros((self.nn, self.num_max_dims * self.num_max_phases)) # phase fluxes in xyz-dirs
        self._Qx = np.zeros((nx + 1, ny, nz)) # total flux in x-dir
        self._Qy = np.zeros((nx, ny + 1, nz)) # total flux in y-dir
        self._Qz = np.zeros((nx, ny, nz + 1)) # total flux in z-dir

        # Store phase fluxes at active cells
        for i, key in enumerate(self._flux_keys):
            if d_fluxes[key].size:
                self._q_xyz[self.actnum_bool, i] = d_fluxes[key]

        # Compute total flux for xyz dirs
        Qxyz_flattened = np.array([])
        if nx > 1:
            self._Qx[1:nx + 1, :, :] = self._total_dir_flux(self._q_xyz, 1).reshape(nx, ny, nz, order="F")
            Qxyz_flattened = np.append(Qxyz_flattened, self._Qx.ravel(order="F"))
        if ny > 1:
            self._Qy[:, 1:ny + 1, :] = self._total_dir_flux(self._q_xyz, 2).reshape(nx, ny, nz, order="F")
            Qxyz_flattened = np.append(Qxyz_flattened, self._Qy.ravel(order="F"))
        if not self.single_layer:
            self._Qz[:, :, 1:nz + 1] = self._total_dir_flux(self._q_xyz, 3).reshape(nx, ny, nz, order="F")
            Qxyz_flattened = np.append(Qxyz_flattened, self._Qz.ravel(order="F"))

        # Append total flux for NNCs if applicable
        if self.NNC and d_NNC_fluxes:
            Qxyz_flattened = np.append(Qxyz_flattened, sum(d_NNC_fluxes[key] for key in d_NNC_fluxes if d_NNC_fluxes[key].size))

        self._Qxyz_flattened = Qxyz_flattened[self._valid_conx_idx]


    def compute_outflow(self, I: int, J: int, K: int) -> float:
        """Computes outflow at a given grid cell (I, J, K).

        Args:
            I (int): I-index of the grid cell.
            J (int): J-index of the grid cell.
            K (int): K-index of the grid cell.

        Returns:
            float: Outflow at the grid cell. Positive: injection, negative: production.
        """
        outflow = 0.
        if self.nx > 1:
            outflow +=  self._Qx[I, J - 1, K - 1]     # positive x-dir flux at I, J, K
            outflow += -self._Qx[I - 1, J - 1, K - 1] # positive x-dir flux at I-1, J, K
        if self.ny > 1:
            outflow +=  self._Qy[I - 1, J, K - 1]     # positive y-dir flux at I, J, K
            outflow += -self._Qy[I - 1, J - 1, K - 1] # positive y-dir flux at I, J-1, K
        if not self.single_layer:
            outflow +=  self._Qz[I-1, J - 1, K]       # positive z-dir flux at I, J, K
            outflow += -self._Qz[I-1, J - 1, K - 1]   # positive z-dir flux at I, J, K-1

        return outflow


    # ---- Private Methods ---------------------------------------------------------------------------------------------


    def _set_dual_poro(self, dp_flag: int) -> None:
        """Configures the grid for dual porosity.

        Args:
            dp_flag (int): Dual porosity flag (0 for single porosity, 1 or 2 for dual porosity).
        """
        self.dual_poro = False
        if dp_flag == 0:
            logging.info(f"Single porosity model detected.")
        else:
            if dp_flag in [1, 2]:  # Valid dual poro flags
                logging.info(f"Dual-porosity model detected.")
                self.dual_poro = True
                if self.nz == 2:
                    self.single_layer = True
            else:
                logging.warning(f"Invalid dual porosity flag found: {dp_flag}. Proceeding with single porosity assumption.")


    def _set_NNC(self, dict_NNC: dict) -> None:
        """Configures the grid for NNCs.

        Args:
            dict_NNC (dict): Dictionary containing egrid data (NNC1, NNC2).
        """
        self.NNC = False
        self.NNC1, self.NNC2 = np.array([]), np.array([])
        self.num_NNCs = 0
        if dict_NNC["NNC1"].size:
            self.NNC = True
            self.NNC1 = dict_NNC["NNC1"]
            self.NNC2 = dict_NNC["NNC2"]
            self.num_NNCs = len(self.NNC1)
            logging.info(f"Found {self.num_NNCs} non-neighbor connections.")


    def _compute_connections(self) -> np.ndarray:
        """Computes the connection matrix
           conx (np.ndarray): connextion matrix. Each row represents a connection
                              between two grid cells.
        """

        # Compute active cell indexing
        cell_idx = np.ones(self.nn, dtype=int)
        cell_idx[self.actnum == 0] = 0
        cell_idx_cumsum = np.cumsum(cell_idx)
        cell_idx_cumsum[self.actnum == 0] = 0

        # Reshape active grid indices into 3D
        cell_idx_3D = cell_idx_cumsum.reshape(self.nx, self.ny, self.nz, order="F")

        # Extend face indexing by adding ghost layers
        face_idx = np.zeros((self.nx + 2, self.ny + 2, self.nz + 2), dtype=int)
        face_idx[1:self.nx + 1, 1:self.ny + 1, 1:self.nz + 1] = cell_idx_3D

        conx = []
        if self.nx > 1: # X-direction connections
            idx1 = face_idx[:self.nx + 1, 1:self.ny + 1, 1:self.nz + 1]
            idx2 = face_idx[1:self.nx + 2, 1:self.ny + 1, 1:self.nz + 1]
            conx.append(np.column_stack((idx1.ravel(order="F"), idx2.ravel(order="F"))))

        if self.ny > 1: # Y-direction connections
            idx1 = face_idx[1:self.nx + 1, :self.ny + 1, 1:self.nz + 1]
            idx2 = face_idx[1:self.nx + 1, 1:self.ny + 2, 1:self.nz + 1]
            conx.append(np.column_stack((idx1.ravel(order="F"), idx2.ravel(order="F"))))

        if not self.single_layer: # Z-direction connections. Use this flag, instead of nz because nz = 2*nz in DP systems
            idx1 = face_idx[1:self.nx + 1, 1:self.ny + 1, :self.nz + 1]
            idx2 = face_idx[1:self.nx + 1, 1:self.ny + 1, 1:self.nz + 2]
            conx.append(np.column_stack((idx1.ravel(order="F"), idx2.ravel(order="F"))))

        # Stack all connections into a single array
        conx = np.vstack(conx)

        # Non-neighboring connections (NNC)
        if self.NNC and self.NNC1.size > 0 and self.NNC2.size > 0:
            cell_idx_flattened = cell_idx_3D.ravel(order="F")
            NNC_conx = np.column_stack((cell_idx_flattened[self.NNC1 - 1], cell_idx_flattened[self.NNC2 - 1]))
            conx = np.vstack((conx, NNC_conx))

        # **Filter out boundary connections**
        self._valid_conx_idx = ~np.any(conx == 0, axis=1)
        self._conx = conx[self._valid_conx_idx]


    def _initialize_flux_keys(self) -> None:
        """Initializes the flux keys for standard and non-neighbor connections."""
        self._flux_keys = ["FLROILI+", "FLROILJ+", "FLROILK+",
                           "FLRWATI+", "FLRWATJ+", "FLRWATK+",
                           "FLRGASI+", "FLRGASJ+", "FLRGASK+"] # all posible flux keys (standard connections)
        self._NNC_flux_keys = ["FLROILN+", "FLRWATN+", "FLRGASN+"] # all posible flux keys (NNCs)


    def _initialize_fvf_keys(self) -> None:
        """Initializes the inverse of formation volume factor (STB/RB)."""
        self._inv_fvf_keys = ["1OVERBO", "1OVERBW", "1OVERBG"]


    def _total_dir_flux(self, q_xyz: np.ndarray, dir_id: int) -> np.ndarray:
        """Computes total flux in a specific direction.

        Args:
            q_xyz (np.ndarray): Flux array.
            dir_id (int): Direction index (1: x, 2: y, 3: z).

        Returns:
            np.ndarray: Total flux values in the specified direction.
        """
        return np.sum(q_xyz[:, dir_id - 1:: self.num_max_dims], axis=1)
