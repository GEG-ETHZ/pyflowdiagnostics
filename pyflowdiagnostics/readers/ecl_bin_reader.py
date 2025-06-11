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

import numpy as np
import struct
import logging
import os
from collections import defaultdict
from datetime import datetime

__all__ = ["EclReader", ]


def __dir__():
    return __all__


class EclReader:
    """Reads SLB ECLIPSE style binary output files (.INIT, .EGRID, .UNRST, .X00xx).

    This class provides methods to read various ECLIPSE output files, including
    initial conditions (.INIT), grid data (.EGRID), and restart files (.UNRST, .X00xx).
    It handles endianness detection and data type conversion.

    Attributes:
        input_file_path (str): Path to the main ECLIPSE input file (.DATA or .IXF).
        input_file_path_base (str): Base path of the input file (without extension).
        init_file_path (str): Path to the initial conditions file (.INIT).
        egrid_file_path (str): Path to the grid data file (.EGRID).
        unrst_file_path (str): Path to the unified restart file (.UNRST).  Currently not used.
    """


    def __init__(self, input_file_path: str) -> None:
        """Initializes the EclReader object.

        Args:
            input_file_path (str): Path to the main ECLIPSE input file (.DATA or .AFI).

        Raises:
            FileNotFoundError: If the input file or any required related file is not found.
            RuntimeError: If the input file has an unsupported extension.
        """
        self.input_file_path = input_file_path
        self._validate_input_file()
        self._initialize_file_names()


    def read_init(self, keys: list = None) -> dict:
        """Reads data from the initial conditions file (.INIT).

        Args:
            keys (list, optional): List of keys to read. If None, all keys are read. Defaults to None.

        Returns:
            dict: Dictionary containing the requested data, keyed by the provided keys.
                Returns an empty dictionary if no keys are provided.
        """
        return self._read_bin(self.init_file_path, keys)


    def read_egrid(self, keys: list = None) -> dict:
        """Reads data from the grid data file (.EGRID).

        Args:
            keys (list, optional): List of keys to read. If None, all keys are read. Defaults to None.

        Returns:
            dict: Dictionary containing the requested data, keyed by the provided keys.
                Returns an empty dictionary if no keys are provided.
        """
        return self._read_bin(self.egrid_file_path, keys)


    def read_rst(self, keys: list = None, tstep_id: int = None) -> dict:
        """Reads data from a restart file (UNRST or .X00xx).

        Args:
            keys (list, optional): List of keys to read. If None, all keys are read. Defaults to None.
            tstep_id (int, optional): Time step ID. Required for reading restart files. Defaults to None.

        Returns:
            dict: Dictionary containing the requested data, keyed by the provided keys.
                Returns an empty dictionary if no keys are provided.

        Raises:
            NotImplementedError: If `unified` is True (UNRST support not implemented).
            ValueError: If `tstep_id` is None.
            FileNotFoundError: If the specified restart file is not found.
        """

        if tstep_id is None:
            raise ValueError("Missing required argument: tstep_id.")

        if self.unrst_file_path is not None:
            data = self._read_unrst(self.unrst_file_path, keys)
            d_out = {}
            for key in keys:
                if tstep_id >= len(data.get(key, [])):
                    d_out[key] = np.array([])
                else:
                    d_out[key] = data[key][tstep_id]
            return d_out

        return self.read_rst_step(keys, tstep_id)


    def read_rst_step(self, keys: list = None, tstep_id: int = None) -> dict:
        file_path = f"{self.input_file_path_base}.X{self._int2ext(tstep_id)}"
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Restart file not found: {file_path}")
        return self._read_bin(file_path, keys)


    def read_unrst(self, file_path: str, keys: list = None, tstep_id: int = None) -> dict:
        result_dict = {"TIME": [], "DATE": []}
        if keys:
            for key in keys:
                result_dict[key] = []

        time_steps = []

        with open(file_path, 'rb') as fid:
            endian = self._detect_endian(fid)
            current_position = fid.tell()
            cumulative_days = 0

            # 1. Index all timesteps
            while True:
                data, _, key = self._load_vector(fid, endian)
                key = key.strip()

                if key == "SEQNUM":
                    time_steps.append((data[0], current_position))

                current_position = fid.tell()
                if fid.tell() >= os.fstat(fid.fileno()).st_size:
                    break

            # print("Raw SEQNUM values:", [s for s, _ in time_steps])

            # Fix: SEQNUM marks the next timestep, so shift by -1
            # time_steps = [(max(0, seqnum - 1), pos) for seqnum, pos in time_steps]

            def read_one_timestep(fid, pos):
                fid.seek(pos)
                result = {}
                found_keys = {k: False for k in keys} if keys else {}

                while keys is None or not all(found_keys.values()):
                    data, _, key = self._load_vector(fid, endian)
                    key = key.strip()

                    if key == "INTEHEAD":
                        IDAY, IMON, IYEAR = data[64], data[65], data[66]
                        result["DATE"] = datetime(IYEAR, IMON, IDAY)

                        if keys and "INTEHEAD" in found_keys:
                            result["INTEHEAD"] = data
                            found_keys["INTEHEAD"] = True

                    elif keys and key in found_keys:
                        if isinstance(data, np.ndarray):
                            result[key] = data
                        elif isinstance(data, (bytes, str)):
                            result[key] = data.decode(errors="ignore").strip()
                        elif isinstance(data, (int, float)):
                            result[key] = np.array([data], dtype=np.float32)
                        else:
                            result[key] = data
                        found_keys[key] = True

                    if fid.tell() >= os.fstat(fid.fileno()).st_size:
                        break

                # Fill missing keys with empty numpy arrays
                if keys:
                    for k in keys:
                        if k not in result:
                            result[k] = np.array([])

                return result

            # 2. Read specific timestep
            if tstep_id is not None:
                match = [t for t in time_steps if t[0] == tstep_id]
                if not match:
                    raise ValueError(f"Timestep {tstep_id} not found in {file_path}")
                step_data = read_one_timestep(fid, match[0][1])
                # Only return requested keys
                if keys:
                    return {k: step_data.get(k, np.array([])) for k in keys}
                else:
                    return step_data

            # 3. Read all timesteps
            previous_date = None
            for step, pos in time_steps:
                step_data = read_one_timestep(fid, pos)

                # Track DATE and TIME
                if "DATE" in step_data:
                    curr_date = step_data["DATE"]
                    if previous_date is None:
                        cumulative_days = 0
                    else:
                        cumulative_days += (curr_date - previous_date).days
                    previous_date = curr_date

                    result_dict["TIME"].append(cumulative_days)
                    result_dict["DATE"].append(curr_date)

                # Append each key, even if data is missing
                if keys:
                    for key in keys:
                        value = step_data.get(key, np.array([]))
                        result_dict[key].append(value)

        return result_dict

    from collections import defaultdict
    from datetime import datetime
    import os
    import numpy as np

    def _read_unrst(self, file_path: str, keys: list = None, tstep_id: int = None) -> dict:
        def read_one_timestep(fid, pos, endian, keys):
            """Reads a full timestep starting at position `pos`."""
            fid.seek(pos)
            result_tmp = {}

            while True:
                data, _, key = self._load_vector(fid, endian)
                key = key.strip()

                if key == "INTEHEAD":
                    IDAY, IMON, IYEAR = data[64], data[65], data[66]
                    result_tmp["DATE"] = datetime(IYEAR, IMON, IDAY)
                    result_tmp["INTEHEAD"] = data  # Keep as np.ndarray

                elif isinstance(data, np.ndarray):
                    result_tmp[key] = data
                elif isinstance(data, (bytes, str)):
                    result_tmp[key] = data.decode(errors="ignore").strip() if isinstance(data, bytes) else data.strip()
                else:
                    result_tmp[key] = np.array([data])

                if fid.tell() >= os.fstat(fid.fileno()).st_size:
                    break

                peek_pos = fid.tell()
                try:
                    _, _, next_key = self._load_vector(fid, endian)
                    if next_key.strip() == "SEQNUM":
                        break
                except Exception:
                    break
                fid.seek(peek_pos)

            if keys is not None:
                result_tmp = {k: v for k, v in result_tmp.items() if k in keys or k == "DATE"}

            return result_tmp

        result_dict = defaultdict(list)
        time_steps = []

        with open(file_path, 'rb') as fid:
            endian = self._detect_endian(fid)
            file_size = os.fstat(fid.fileno()).st_size

            while fid.tell() < file_size:
                pos = fid.tell()
                data, _, key = self._load_vector(fid, endian)
                if key.strip() == "SEQNUM":
                    time_steps.append((data[0], pos))

        # Initialize result_dict with empty lists for all requested keys
        if keys:
            for k in keys:
                result_dict[k] = []

        if tstep_id is not None:
            match = [t for t in time_steps if t[0] == tstep_id]
            if not match:
                raise ValueError(f"Timestep {tstep_id} not found in {file_path}")
            with open(file_path, 'rb') as fid:
                return read_one_timestep(fid, match[0][1], endian, keys)

        cumulative_days = 0
        previous_date = None

        for step, pos in time_steps:
            with open(file_path, 'rb') as fid_inner:
                result = read_one_timestep(fid_inner, pos, endian, keys)

            if "DATE" in result:
                current_date = result["DATE"]
                if previous_date:
                    cumulative_days += (current_date - previous_date).days
                result_dict["TIME"].append(cumulative_days)
                result_dict["DATE"].append((current_date.year, current_date.month, current_date.day, 0, 0))
                previous_date = current_date

            for k in keys or result.keys():
                if k in result:
                    result_dict[k].append(result[k])

        # Ensure all explicitly requested keys that were never found remain empty
        if keys:
            for k in keys:
                if k not in result_dict:
                    result_dict[k] = []

        return dict(result_dict)


    # ---- Private Methods ---------------------------------------------------------------------------------------------


    def _validate_input_file(self) -> None:
        """Validates the input file and its extension.

        Raises:
            FileNotFoundError: If the input file is not found.
            RuntimeError: If the input file has an unsupported extension.
        """
        if not os.path.exists(self.input_file_path):
            raise FileNotFoundError(f"Input file not found: {self.input_file_path}")

        base, ext = os.path.splitext(self.input_file_path)
        if ext.upper() not in [".DATA", ".IXF"]:
            if ext.upper() == ".AFI":
                logging.warning("Intersect input file detected. Limited support available.")
            else:
                raise RuntimeError(f"Unsupported input file: {self.input_file_path}")

        self.input_file_path_base = base


    def _initialize_file_names(self) -> None:
        """Initializes file paths for related binary files (.INIT, .EGRID, .UNRST).

        Raises:
            FileNotFoundError: If any of the required files (.INIT, .EGRID) are not found.
        """

        def find_file_with_known_cases(base: str, ext: str) -> str:
            for suffix in [ext.upper(), ext.lower()]:
                candidate = f"{base}.{suffix}"
                if os.path.exists(candidate):
                    return candidate
            raise FileNotFoundError(f"Required file not found: {base}.{ext} (tried {ext.upper()} and {ext.lower()})")

        self.init_file_path = find_file_with_known_cases(self.input_file_path_base, "INIT")
        self.egrid_file_path = find_file_with_known_cases(self.input_file_path_base, "EGRID")
        self.unrst_file_path = None
        for suffix in ["UNRST", "unrst"]:
            candidate = f"{self.input_file_path_base}.{suffix}"
            if os.path.exists(candidate):
                self.unrst_file_path = candidate
                break


    def _read_bin(self, file_path: str, keys: list) -> dict:
        """Reads ECLIPSE style binary data from the given file.

        Args:
            file_path (str): Path to the binary file.
            keys (list): List of keys to read.

        Returns:
            dict: Dictionary containing the requested data. Returns an empty dictionary if keys is None.
        """

        if keys is None:
            logging.warning("No keys provided.")
            return {}

        logging.debug(f"Reading keys: {keys} in file: {file_path}")

        variables = {}
        with open(file_path, 'rb') as fid:
            endian = self._detect_endian(fid)
            found_keys = {key: False for key in keys}

            while keys and not all(found_keys.values()):
                data, _, key = self._load_vector(fid, endian)
                key = key.strip()
                if key in found_keys:
                    # Dynamically determine dtype
                    if isinstance(data, np.ndarray):
                        variables[key] = data  # Keep original dtype
                    elif isinstance(data, (bytes, str)):
                        variables[key] = data.decode(errors="ignore").strip()  # Convert bytes to string
                    elif isinstance(data, (int, float)):
                        variables[key] = np.array([data], dtype=np.float32)  # Convert scalars to array
                    else:
                        logging.warning(f"Unknown data type for key: {key}")
                        variables[key] = data  # Store as-is

                    found_keys[key] = True

                if fid.tell() >= os.fstat(fid.fileno()).st_size:
                    break

            # Log missing keys (Debug level)
            missing_keys = [k for k, v in found_keys.items() if not v]
            if missing_keys:
                logging.debug(f"The following keys were not found: {missing_keys}")
                for key in missing_keys:
                    variables[key] = np.array([])

        return variables


    def _load_vector(self, fid, endian):
        """Reads a data block (vector) from the binary file.

        Args:
            fid: File object.
            endian (str): Endianness ('<' for little-endian, '>' for big-endian).

        Returns:
            tuple: A tuple containing the data (NumPy array or string), the data count, and the key.
                Returns (None, None, key) if an error occurs during reading.
        """
        try:
            # Read and verify the header
            header_size = struct.unpack(endian + 'i', fid.read(4))[0]
            key = fid.read(8).decode(errors='ignore').strip()
            data_count = struct.unpack(endian + 'i', fid.read(4))[0]
            data_type_raw = fid.read(4)
            data_type = data_type_raw.decode(errors='ignore').strip().upper()
            end_size = struct.unpack(endian + 'i', fid.read(4))[0]

            if header_size != end_size:
                logging.warning(f"Mismatch Detected for {key}: Header={header_size}, End={end_size}")
                return None, None, key  # Skip this entry

            # Define data type mapping
            dtype_map = {'CHAR': 'S1', 'INTE': 'i4', 'REAL': 'f4', 'DOUB': 'f8', 'LOGI': 'i4'}
            dtype = dtype_map.get(data_type)

            if dtype:
                raw_data = bytearray()
                read_count = 0

                while read_count < data_count:
                    # Read the header size of this chunk
                    chunk_size = struct.unpack(endian + 'i', fid.read(4))[0]
                    chunk_data = fid.read(chunk_size)
                    chunk_end = struct.unpack(endian + 'i', fid.read(4))[0]

                    if chunk_size != chunk_end:
                        logging.warning(f"Chunk mismatch in {key}: Expected {chunk_size}, got {chunk_end}")
                        return None, None, key

                    raw_data.extend(chunk_data)
                    read_count += chunk_size // np.dtype(dtype).itemsize

                if data_type == "CHAR":
                    char_array = np.frombuffer(raw_data, dtype="S1").reshape((-1, 8))  # 8-char wide strings
                    char_array = np.char.decode(char_array, encoding='utf-8').astype(str)
                    return char_array, data_count, key
                else:
                    data = np.frombuffer(raw_data, dtype=endian + dtype)
                    return data, data_count, key
            else:
                fid.seek(data_count * 4, os.SEEK_CUR)  # Skip unknown type
                return None, None, key
        except struct.error:
            return None, None, ""


    def _detect_endian(self, fid):
        """Detects file endianness.

        Args:
            fid: File object.

        Returns:
            str: Endianness ('<' for little-endian, '>' for big-endian).
        """
        fid.seek(0)
        test_int = fid.read(4)
        little_endian = struct.unpack('<i', test_int)[0]
        big_endian = struct.unpack('>i', test_int)[0]
        fid.seek(0)
        return '<' if abs(little_endian) < abs(big_endian) else '>'


    def _int2ext(self, i):
        """Converts an integer to a formatted string with leading zeros (e.g., 1 to "0001").

        Args:
            i (int): Integer to convert.

        Returns:
            str: Formatted string with leading zeros.
        """
        return f"{i:04d}"
