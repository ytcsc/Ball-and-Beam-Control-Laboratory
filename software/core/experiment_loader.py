import csv
import numpy as np

from .message_handler import MessageHandler


class ExperimentLoader:
    """Loads and validates experiment datapoints from CSV files.

    The CSV file must contain two columns:
        - time_s (float): elapsed time in seconds.
        - spx_cm (float): setpoint position in centimeters.
    """

    # Experiment CSV parameters
    EXPERIMENT_HEADER = ['time_s', 'spx_cm']            # Expected experiment CSV header
    EXPERIMENT_MIN_DTIME = 0.001                        # Minimum time difference in seconds between successive data points
    EXPERIMENT_MAX_TIME = 30*60                         # Maximum experiment time in seconds
    EXPERIMENT_MAX_BEAM_LENGTH = 50                     # Maximum beam length in cm
    EXPERIMENT_DATA_LENGTH = len(EXPERIMENT_HEADER)     # Expected data length for each csv row

    # Error and warning codes
    LOADER_ERROR_EMPTY_FILE = 301                       # Empty CSV file
    LOADER_ERROR_INCORRECT_HEADER = 302                 # CSV file has incorrect header
    LOADER_ERROR_NO_DATA = 303                          # CSV file has no data
    LOADER_ERROR_MIN_DATAPOINTS = 304                   # CSV file has fewer than the minimum required datapoints
    LOADER_ERROR_INSUFFICIENT_DT = 305                  # CSV datapoints violate the minimum sampling time interval
    LOADER_ERROR_INVALID_ROW = 306                      # A data row is empty or has an incorrect number of columns
    LOADER_ERROR_INVALID_VALUE = 307                    # A data value cannot be parsed or violates a required numerical constraint
    LOADER_ERROR_FILE_ACCESS = 308                      # An operating-system error occurred while opening or reading the file
    LOADER_FILEPATH_ERROR = 309                         # The specified path does not point to an existing file

    LOADER_WARNING_BEAM_EXCEEDED = 351                  # Experiment contains a position setpoint exceeding beam length
    LOADER_WARNING_TIME_TOO_LARGE = 352                 # Total duration of the experiment exceeds the limit

    def __init__(self):
        """Initialize the loader and allocate its data buffer."""
        self.times: np.ndarray = np.array([], dtype=np.float64)
        self.setpoints: np.ndarray = np.array([], dtype=np.float64)
        self._count: int = 0
        self.msg_handler: MessageHandler = MessageHandler()

    def load(self, filepath: str, csv_delimiter: str = ',') -> None:
        """Load and validate experimental data from a CSV file.

        The file must contain the expected header and at least two valid
        data points. Each point must have a valid timestamp and position.
        Consecutive timestamps must differ by at least EXPERIMENT_MIN_DTIME.

        Args:
            filepath: Path to the CSV file.
            csv_delimiter: Single-character delimiter used in the CSV file.
        """
        self.reinitialize()

        rawtimes: list[float] = []
        rawsetpoints: list[float] = []

        try:
            with open(filepath, mode='r', encoding='utf-8', newline='') as experiment_file:
                reader = csv.reader(experiment_file, delimiter=csv_delimiter)
                header = next(reader, None)

                if not header:
                    self.msg_handler.add_msg(self.LOADER_ERROR_EMPTY_FILE)
                    return
                if header != self.EXPERIMENT_HEADER:
                    self.msg_handler.add_msg(self.LOADER_ERROR_INCORRECT_HEADER)
                    return

                for row in reader:
                    if not row or all(not field for field in row):
                        self.msg_handler.add_msg(self.LOADER_ERROR_INVALID_ROW)
                        self.reinitialize()
                        return
                    if len(row) != self.EXPERIMENT_DATA_LENGTH:
                        self.msg_handler.add_msg(self.LOADER_ERROR_INVALID_ROW)
                        self.reinitialize()
                        return
                    
                    try:
                        time_val = float(row[0])
                        spx_val = float(row[1])
                    except (ValueError, OverflowError):
                        self.msg_handler.add_msg(self.LOADER_ERROR_INVALID_VALUE)
                        self.reinitialize()
                        return
                    
                    if not (np.isfinite(time_val) and np.isfinite(spx_val)):
                        self.msg_handler.add_msg(self.LOADER_ERROR_INVALID_VALUE)
                        self.reinitialize()
                        return

                    rawtimes.append(time_val)
                    rawsetpoints.append(spx_val)
                    
        except FileNotFoundError:
            self.msg_handler.add_msg(self.LOADER_FILEPATH_ERROR)
            return     
        except OSError:
            self.msg_handler.add_msg(self.LOADER_ERROR_FILE_ACCESS)
            return

        count = len(rawtimes)
        if count == 0:
            self.msg_handler.add_msg(self.LOADER_ERROR_NO_DATA)
            return
        if count < 2:
            self.msg_handler.add_msg(self.LOADER_ERROR_MIN_DATAPOINTS)
            return

        times_arr = np.array(rawtimes, dtype=np.float64)
        setpoints_arr = np.array(rawsetpoints, dtype=np.float64)

        if np.any(times_arr < 0):
            self.msg_handler.add_msg(self.LOADER_ERROR_INVALID_VALUE)
            return

        if np.any(np.diff(times_arr) < self.EXPERIMENT_MIN_DTIME):
            self.msg_handler.add_msg(self.LOADER_ERROR_INSUFFICIENT_DT)
            return
        
        if np.any((setpoints_arr < 0) | (setpoints_arr > self.EXPERIMENT_MAX_BEAM_LENGTH)):
            self.msg_handler.add_msg(self.LOADER_WARNING_BEAM_EXCEEDED)
        
        if times_arr[-1] > self.EXPERIMENT_MAX_TIME:
            self.msg_handler.add_msg(self.LOADER_WARNING_TIME_TOO_LARGE)

        self.times = times_arr
        self.setpoints = setpoints_arr
        self._count = count

    def get_setpoint(self, time_s: float) -> float | None:
        """Calculate the setpoint for a given time using linear interpolation.

        Extrapolates out-of-bounds queries by clamping to the initial or final
        setpoint values.

        Args:
            time_s (float): Query timestamp in seconds.

        Returns:
            float | None: Interpolated setpoint in cm, or None if no valid experiment is loaded.
        """
        if not self.has_data():
            return None

        return float(np.interp(time_s, self.times, self.setpoints))

    def has_data(self) -> bool:
        """Check whether valid experiment data is currently loaded.

        Returns:
            bool: True if valid experiment data exists, False otherwise.
        """
        return self._count >= 2

    def reinitialize(self) -> None:
        """Reset loader data structures while retaining recorded errors."""
        self.times = np.array([], dtype=np.float64)
        self.setpoints = np.array([], dtype=np.float64)
        self._count = 0