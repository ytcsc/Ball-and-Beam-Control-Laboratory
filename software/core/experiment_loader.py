import csv
import numpy as np


class ExperimentLoader:
    """
    Loads, validates, and provides access to experiment data stored in a CSV
    file.

    The CSV file must contain two columns:
        - time_ms (int): elapsed time in milliseconds.
        - spx_cm (float): setpoint position in centimeters.

    Errors and warnings are stored in a pre-allocated list of fixed size (20
    elements, initialized to 0) with a current index pointer. Recorded error
    and warning codes can be appended to a user-provided integer list using
    get_errors_and_warnings().
    """

    # Experiment CSV parameters
    EXPERIMENT_HEADER = ['time_ms', 'spx_cm']           # Expected experiment CSV header
    EXPERIMENT_MIN_DTIME = 20                           # Minimum time difference in ms between successive data points
    EXPERIMENT_MAX_TIME = 30*60*1000                    # Maximum experiment time in ms
    EXPERIMENT_MAX_BEAM_LENGTH = 50                     # Maximum beam length in cm
    EXPERIMENT_MAX_DATAPOINTS = 65536                   # Maximum number of experiment datapoints
    LOADER_MAX_ERRORS = 20                              # Maximum number of error and warning codes stored
    EXPERIMENT_DATA_LENGTH = len(EXPERIMENT_HEADER)     # Expected data length for each csv row

    # Error and warning codes
    LOADER_ERROR_EMPTY_FILE = 101                       # Empty CSV file
    LOADER_ERROR_INCORRECT_HEADER = 102                 # CSV file has incorrect header
    LOADER_ERROR_NO_DATA = 103                          # CSV file has no data
    LOADER_ERROR_MAX_DATAPOINTS = 104                   # CSV file exceeds maximum number of datapoints
    LOADER_ERROR_MIN_DATAPOINTS = 105                   # CSV file has fewer than the minimum required datapoints
    LOADER_ERROR_INSUFFICIENT_DT = 106                  # CSV datapoints violate the minimum sampling time interval
    LOADER_ERROR_INVALID_ROW = 107                      # A data row is empty or has an incorrect number of columns
    LOADER_ERROR_INVALID_VALUE = 108                    # A data value cannot be parsed or violates a required numerical constraint
    LOADER_ERROR_FILE_ACCESS = 109                      # An operating-system error occurred while opening or reading the file
    LOADER_FILEPATH_ERROR = 110                         # The specified path does not point to an existing file

    LOADER_WARNING_BEAM_EXCEEDED = 151                  # Experiment contains a position setpoint exceeding beam length
    LOADER_WARNING_TIME_TOO_LARGE = 152                 # Total duration of the experiment exceeds the limit

    # NumPy structured-array data type
    DATA_DTYPE = np.dtype([
        ('time_ms', np.int64),
        ('spx_cm', np.float64)])

    def __init__(self):
        """
        Initialize the loader and allocate its data buffer.
        """
        self._buffer = np.zeros(self.EXPERIMENT_MAX_DATAPOINTS, dtype=self.DATA_DTYPE)
        self._count = 0
        self._index = 0
        self._error_codes: list[int] = [0] * self.LOADER_MAX_ERRORS
        self._error_index = 0

    def load(self, filepath: str, csv_delimiter: str = ','):
        """
        Load and validate experimental data from a CSV file.

        The file must contain the expected header and at least two valid
        data points. Each point must have a valid timestamp and position.
        Consecutive timestamps must differ by at least EXPERIMENT_MIN_DTIME.

        Errors and warnings are appended to the FIFO queue. If a loading
        or validation error occurs, the method returns immediately.

        Args:
            filepath: Path to the CSV file.
            csv_delimiter: Single-character delimiter used in the CSV file.

        Returns:
            None. Check the error/warning queue to determine whether
            loading succeeded and whether warnings were generated.
        """
        self._count = 0
        self._index = 0
        self._reset_errors()
        count = 0

        try:
            with open(filepath, mode='r', encoding='utf-8', newline='') as experiment_file:
                reader = csv.reader(experiment_file, delimiter=csv_delimiter)
                header = next(reader, None)
                if not header:
                    self._add_error_codes(self.LOADER_ERROR_EMPTY_FILE)
                    self.reinitialize()
                    return
                if header != self.EXPERIMENT_HEADER:
                    self._add_error_codes(self.LOADER_ERROR_INCORRECT_HEADER)
                    self.reinitialize()
                    return
                for row in reader:
                    if not row or all(not field for field in row):
                        self._add_error_codes(self.LOADER_ERROR_INVALID_ROW)
                        self.reinitialize()
                        return
                    if len(row) != self.EXPERIMENT_DATA_LENGTH:
                        self._add_error_codes(self.LOADER_ERROR_INVALID_ROW)
                        self.reinitialize()
                        return
                    try:
                        time_ms = int(row[0])
                        spx_cm = float(row[1])
                    except (ValueError, OverflowError):
                        self._add_error_codes(self.LOADER_ERROR_INVALID_VALUE)
                        self.reinitialize()
                        return
                    
                    if not np.isfinite(spx_cm):
                        self._add_error_codes(self.LOADER_ERROR_INVALID_VALUE)
                        self.reinitialize()
                        return
                    if count >= self.EXPERIMENT_MAX_DATAPOINTS:
                        self._add_error_codes(self.LOADER_ERROR_MAX_DATAPOINTS)
                        self.reinitialize()
                        return
                    
                    self._buffer[count] = (time_ms, spx_cm)
                    count += 1
        except FileNotFoundError:
            self._add_error_codes(self.LOADER_FILEPATH_ERROR)
            self.reinitialize()
            return     
        except OSError:
            self._add_error_codes(self.LOADER_ERROR_FILE_ACCESS)
            self.reinitialize()
            return
        
        if count == 0:
            self._add_error_codes(self.LOADER_ERROR_NO_DATA)
            self.reinitialize()
            return
        if count < 2:
            self._add_error_codes(self.LOADER_ERROR_MIN_DATAPOINTS)
            self.reinitialize()
            return

        valid_data = self._buffer[:count]
        if np.any(np.diff(valid_data['time_ms']) < self.EXPERIMENT_MIN_DTIME):
            self._add_error_codes(self.LOADER_ERROR_INSUFFICIENT_DT)
            self.reinitialize()
            return
        if np.any(valid_data['time_ms'] < 0):
            self._add_error_codes(self.LOADER_ERROR_INVALID_VALUE)
            self.reinitialize()
            return
        if np.any(np.abs(valid_data['spx_cm']) > self.EXPERIMENT_MAX_BEAM_LENGTH):
            self._add_error_codes(self.LOADER_WARNING_BEAM_EXCEEDED)
        if valid_data['time_ms'][-1] > self.EXPERIMENT_MAX_TIME:
            self._add_error_codes(self.LOADER_WARNING_TIME_TOO_LARGE)

        self._count = count
        self._index = 0

    def get_data(self) -> np.ndarray | None:
        """
        Return a view of all successfully loaded data points.

        The returned array shares memory with the internal buffer, so no
        copy of the records is created. Modifying the returned array also
        modifies the internal data.

        Returns:
            A NumPy structured-array view containing the valid records,
            or None if no valid data exists.
        """
        if self._is_valid():
            return self._buffer[:self._count]
        else:
            return None

    def get_next(self) -> tuple[int, float] | None:
        """
        Return the next data point and advance the iteration index.

        Returns:
            A tuple containing (time_ms, spx_cm) for the next record.
            Returns None when all loaded records have been consumed.
        """
        if self._index >= self._count:
            return None
        row = self._buffer[self._index]
        self._index += 1
        return int(row['time_ms']), float(row['spx_cm'])

    def reset_index(self) -> None:
        """
        Reset the sequential-access index to the first data point.

        The loaded data remains unchanged. The next call to get_next()
        will return the first record again.
        """
        self._index = 0

    def reinitialize(self) -> None:
        """
        Clear the internal data buffer and reset the loader's data state.

        The record count and sequential-access index are reset to zero.
        The error/warning queue is intentionally preserved so that
        previously recorded messages remain available to the caller.
        """
        self._buffer.fill(0)
        self._count = 0
        self._index = 0

    def _is_valid(self) -> bool:
        """
        Determine whether the loader currently contains usable data.

        Returns:
            True if there is valid data; otherwise False.
        """
        if self._count >= 2:
            return True
        else:
            return False

    def _add_error_codes(self, code: int) -> None:
        """
        Store an error or warning code in the pre-allocated error.

        Args:
            code (int): Error or warning code to store.
        """
        if self._error_index < self.LOADER_MAX_ERRORS:
            self._error_codes[self._error_index] = code
            self._error_index += 1

    def _reset_errors(self) -> None:
        """
        Reset the pre-allocated error list to zeros and reset the error index.
        """
        self._error_codes[:] = [0] * self.LOADER_MAX_ERRORS
        self._error_index = 0

    def get_error_codes(self, output_list: list[int]) -> None:
        """
        Append the recorded error and warning codes (up to the current index)
        to the provided integer list.

        Args:
            output_list: List of integers where recorded error/warning codes will be added.
        """
        output_list.extend(self._error_codes[:self._error_index])
        self._reset_errors()