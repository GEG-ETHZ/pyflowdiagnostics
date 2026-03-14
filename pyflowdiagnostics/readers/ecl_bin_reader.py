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

            if not hasattr(self, "_unrst_data"):
                self._unrst_data = {}

            keys_combined = "|".join(sorted(keys))

            if keys_combined in self._unrst_data.keys():
                data = self._unrst_data[keys_combined]
            else:
                data = self.read_unrst(self.unrst_file_path, keys)
                self._unrst_data[keys_combined] = data

            # For UNRST: index 0 is often initial step (no wells); report steps start at 1.
            # So tstep_id=1 (first report step) maps to index 1.
            idx = tstep_id
            d_out = {}
            for key in keys:
                if idx < 0 or idx >= len(data.get(key, [])):
                    d_out[key] = np.array([])
                else:
                    d_out[key] = data[key][idx]
            return d_out

        return self.read_rst_step(keys, tstep_id)


    def read_rst_step(self, keys: list = None, tstep_id: int = None) -> dict:
        file_path = f"{self.input_file_path_base}.X{self._int2ext(tstep_id)}"
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Restart file not found: {file_path}")
        return self._read_bin(file_path, keys)


    def read_unrst(self, file_path: str, keys: list = None, tstep_id: int = None) -> dict:
        """Read UNRST using pattern matching (robust for OPM Flow and Eclipse formats).

        Returns {key: [val_t0, val_t1, ...]} for each requested key, or single timestep
        when tstep_id is specified (used internally by read_unrst with tstep_id=None).
        """
        if keys is None:
            keys = []

        all_results = {}
        file_size = os.path.getsize(file_path)

        with open(file_path, "rb") as fid:
            file_data = fid.read()

        first_int = struct.unpack("<i", file_data[:4])[0]
        endian = "<" if (first_int > 0 and first_int < 1000) else ">"

        # Find all INTEHEAD positions (timestep boundaries)
        intehead_positions = []
        pos = 0
        while True:
            pos = file_data.find(b"INTEHEAD", pos)
            if pos == -1:
                break
            intehead_positions.append(pos - 4)
            pos += 8

        # Find positions for each requested key
        key_positions = {key: [] for key in keys} if keys else {}
        for key in keys:
            pos = 0
            while True:
                pos = file_data.find(key.encode("ascii"), pos)
                if pos == -1:
                    break
                if pos >= 4:
                    try:
                        header_size = struct.unpack(endian + "i", file_data[pos - 4:pos])[0]
                        if 8 <= header_size <= 1000:
                            key_positions[key].append(pos - 4)
                    except (struct.error, IndexError):
                        pass
                pos += len(key)

        with open(file_path, "rb") as fid:
            dates = []
            for intehead_pos in intehead_positions:
                fid.seek(intehead_pos)
                try:
                    header_size = struct.unpack(endian + "i", fid.read(4))[0]
                    key = fid.read(8).decode("ascii", errors="ignore").strip()
                    data_count = struct.unpack(endian + "i", fid.read(4))[0]
                    data_type = fid.read(4).decode("ascii", errors="ignore").strip()
                    end_size = struct.unpack(endian + "i", fid.read(4))[0]
                    if key == "INTEHEAD" and header_size == end_size:
                        raw_data = bytearray()
                        read_count = 0
                        while read_count < data_count:
                            chunk_size = struct.unpack(endian + "i", fid.read(4))[0]
                            chunk_data = fid.read(chunk_size)
                            chunk_end = struct.unpack(endian + "i", fid.read(4))[0]
                            if chunk_size != chunk_end:
                                break
                            raw_data.extend(chunk_data)
                            read_count += chunk_size // 4
                        if len(raw_data) >= data_count * 4:
                            data = np.frombuffer(raw_data, dtype=endian + "i4")
                            if len(data) > 66:
                                IDAY, IMON, IYEAR = data[64], data[65], data[66]
                                dates.append(datetime(IYEAR, IMON, IDAY))
                            else:
                                dates.append(None)
                        else:
                            dates.append(None)
                    else:
                        dates.append(None)
                except Exception:
                    dates.append(None)

        for timestep_idx, (intehead_pos, date) in enumerate(zip(intehead_positions, dates)):
            result = {}
            if date is not None:
                result["DATE"] = date

            with open(file_path, "rb") as fid:
                try:
                    fid.seek(intehead_pos)
                    header_size = struct.unpack(endian + "i", fid.read(4))[0]
                    key = fid.read(8).decode("ascii", errors="ignore").strip()
                    data_count = struct.unpack(endian + "i", fid.read(4))[0]
                    data_type = fid.read(4).decode("ascii", errors="ignore").strip()
                    end_size = struct.unpack(endian + "i", fid.read(4))[0]
                    if key == "INTEHEAD" and header_size == end_size:
                        raw_data = bytearray()
                        read_count = 0
                        while read_count < data_count:
                            chunk_size = struct.unpack(endian + "i", fid.read(4))[0]
                            chunk_data = fid.read(chunk_size)
                            chunk_end = struct.unpack(endian + "i", fid.read(4))[0]
                            if chunk_size != chunk_end:
                                break
                            raw_data.extend(chunk_data)
                            read_count += chunk_size // 4
                        if len(raw_data) >= data_count * 4:
                            result["INTEHEAD"] = np.frombuffer(raw_data, dtype=endian + "i4")
                except Exception:
                    pass

            next_intehead = intehead_positions[timestep_idx + 1] if timestep_idx + 1 < len(intehead_positions) else file_size

            for key in keys:
                if key == "INTEHEAD":
                    continue
                key_pos = None
                if key in key_positions:
                    for p in key_positions[key]:
                        if intehead_pos < p < next_intehead:
                            key_pos = p
                            break
                if key_pos is None:
                    result[key] = np.array([])
                    continue
                with open(file_path, "rb") as fid:
                    fid.seek(key_pos)
                    try:
                        header_size = struct.unpack(endian + "i", fid.read(4))[0]
                        key_name = fid.read(8).decode("ascii", errors="ignore").strip()
                        data_count = struct.unpack(endian + "i", fid.read(4))[0]
                        data_type = fid.read(4).decode("ascii", errors="ignore").strip()
                        end_size = struct.unpack(endian + "i", fid.read(4))[0]
                        if key_name != key or header_size != end_size:
                            result[key] = np.array([])
                            continue
                        bytes_per_element = 8 if data_type == "CHAR" else 4
                        total_bytes = data_count * bytes_per_element
                        raw_data = bytearray()
                        bytes_read = 0
                        while bytes_read < total_bytes:
                            chunk_size = struct.unpack(endian + "i", fid.read(4))[0]
                            chunk_data = fid.read(chunk_size)
                            chunk_end = struct.unpack(endian + "i", fid.read(4))[0]
                            if chunk_size != chunk_end:
                                break
                            raw_data.extend(chunk_data)
                            bytes_read += chunk_size
                        if len(raw_data) >= total_bytes:
                            if data_type == "CHAR":
                                char_data = np.frombuffer(raw_data, dtype="S1").reshape((-1, 8))
                                result[key] = np.char.decode(char_data, encoding="ascii").astype(str)
                            else:
                                dtype_map = {"REAL": "f4", "DOUB": "f8", "INTE": "i4", "LOGI": "i4"}
                                dtype = dtype_map.get(data_type, "f4")
                                result[key] = np.frombuffer(raw_data, dtype=endian + dtype)
                        else:
                            result[key] = np.array([])
                    except Exception:
                        result[key] = np.array([])

            all_results[timestep_idx] = result

        # Convert to {key: [val_t0, val_t1, ...]} for read_rst
        result_dict = defaultdict(list)
        for idx in sorted(all_results.keys()):
            r = all_results[idx]
            for k in keys:
                result_dict[k].append(r.get(k, np.array([])))
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
        if ext.upper() not in [".DATA", ".AFI"]:
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
