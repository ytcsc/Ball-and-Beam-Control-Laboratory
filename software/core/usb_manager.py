import serial
from serial.tools import list_ports

from .message_handler import MessageHandler

class USBManager:
    """Manage low-level USB CDC serial communication with the hardware."""

    # Error and warning codes
    USB_DEVICE_NOT_FOUND = 101              # Device was not found
    USB_CONNECTION_FAILED = 102             # USB connection failed
    USB_DISCONNECTION_FAILED = 103          # USB disconnection (closing port) failed
    USB_NOT_CONNECTED = 104                 # USB is not connected
    USB_WRITE_ERROR = 105                   # USB write error
    USB_READ_ERROR = 106                    # USB read error
    USB_READ_TIMEOUT = 107                  # Read timeout

    def __init__(self, timeout: float = 0.005):
        """Initialize USBManager parameters and internal buffers.

        Args:
            timeout: Read and write timeout in seconds, applied to the serial
            connection.
        """
        self.port: str | None = None
        self.baudrate: int = 115200  # This value is ignored by the USB CDC
        self.timeout: float = timeout
        self.vid: int = 0x2E8A
        self.pid: int = 0x0005
        self.product_name: str = "ytcsc-bcl"
        self._ser: serial.Serial | None = None
        self.msg_handler = MessageHandler()

    def connect(self) -> bool:
        """Locate the target hardware and establish a USB CDC connection.

        Search for a device matching the configured VID, PID, and product
        name, then open its serial port. Any errors encountered during 
        connection are appended to the internal error/warning queue.

        Returns:
            bool: True if connection succeeded, False otherwise.
        """
        ports = list_ports.comports()
        target_port = None
        
        for p in ports:
            if p.vid == self.vid and p.pid == self.pid and p.product is not None and self.product_name in p.product:
                target_port = p.device
                break
        
        if target_port is None:
            self.msg_handler.add_msg(self.USB_DEVICE_NOT_FOUND)
            return False
       
        if self.is_connected():
            self.close()
        
        try:
            self._ser = serial.Serial(
                port=target_port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout)
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
            self.port = target_port
            return True
        except (serial.SerialException, OSError):
            self._ser = None
            self.port = None
            self.msg_handler.add_msg(self.USB_CONNECTION_FAILED)
            return False

    def is_connected(self) -> bool:
        """Check whether the serial port is open.

        Returns:
            bool: True if the serial object exists and its port is open,
                False otherwise.
        """
        return self._ser is not None and self._ser.is_open

    def close(self) -> None:
        """Safely close the active USB serial port."""
        if self._ser is not None:
            try:
                if self._ser.is_open:
                    self._ser.reset_input_buffer()
                    self._ser.reset_output_buffer()
                    self._ser.close()
            except (serial.SerialException, OSError):
                self.msg_handler.add_msg(self.USB_DISCONNECTION_FAILED)
            finally:
                self.port = None
                self._ser = None

    def write(self, raw_bytes: bytes) -> bool:
        """Write raw byte payload to the open serial port.

        Args:
            raw_bytes: Raw bytes to transmit over USB.

        Returns:
            bool: True if transmission succeeded, False otherwise.
        """
        if not self.is_connected() or self._ser is None:
            self.msg_handler.add_msg(self.USB_NOT_CONNECTED)
            return False

        try:
            self._ser.write(raw_bytes)
            return True
        except (serial.SerialException, OSError):
            self.close()
            self.msg_handler.add_msg(self.USB_WRITE_ERROR)
            return False

    def read(self, expected_bytes: int) -> bytes | None:
        """Read requested length of raw bytes from serial buffer.

        Args:
            expected_bytes: Exact number of bytes expected to be read.

        Returns:
            bytes | None: Raw payload if full read succeeds, None on error or timeout.
        """
        if not self.is_connected() or self._ser is None:
            self.msg_handler.add_msg(self.USB_NOT_CONNECTED)
            return None

        try:
            raw_bytes = self._ser.read(expected_bytes)
            if len(raw_bytes) != expected_bytes:
                self.msg_handler.add_msg(self.USB_READ_TIMEOUT)
                return None
            return raw_bytes
        except (serial.SerialException, OSError):
            self.close()
            self.msg_handler.add_msg(self.USB_READ_ERROR)
            return None