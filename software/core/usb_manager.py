import serial
from serial.tools import list_ports

from . import protocol

# Error and warning codes
USB_NO_ERROR = 0                        # No USB error occurred.
USB_DEVICE_NOT_FOUND = 301              # Device was not found
USB_CONNECTION_FAILED = 302             # USB connection failed
USB_NOT_CONNECTED = 303                 # USB is not connected
USB_WRITE_ERROR = 304                   # USB write error
USB_READ_ERROR = 305                    # USB read error
USB_READ_BUFFER_OUT_OF_BOUNDS = 306     # Read exceeds read buffer length


class USBManager:
    """Manage USB CDC serial communication with the hardware."""

    def __init__(self, timeout: float = 0.005):
        """Initialize USBManager parameters and internal buffers.

        Args:
            timeout: Read and write timeout in seconds, applied to the serial connection.
        """
        self.port = None
        self.baudrate = 115200  # This value is ignored by the USB CDC
        self.timeout = timeout
        self.vid = 0x2E8A
        self.pid = 0x0005
        self.product_name = "ytcsc-bcl"
        self._ser: serial.Serial | None = None
        self._read_buffer = bytearray(1 + (len(protocol.PROTOCOL_REGISTER_FORMATS) * 2))

    def connect(self) -> int:
        """Locate the target hardware and establish a USB CDC connection.

        Search for a device matching the configured VID, PID, and product
        name, then open its serial port.

        Returns:
            USB_NO_ERROR (0) on success, or a specific USB error code.
        """
        ports = list_ports.comports()
        target_port = None
        for p in ports:
            if p.vid == self.vid and p.pid == self.pid and p.product is not None and self.product_name in p.product:
                target_port = p.device
        if target_port is None:
            return USB_DEVICE_NOT_FOUND
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
            return USB_NO_ERROR
        except (serial.SerialException, OSError):
            self._ser = None
            self.port = None
            return USB_CONNECTION_FAILED

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
                pass
            finally:
                self.port = None
                self._ser = None

    def transfer(
        self,
        start_write_address: int = 0x00,
        values: list[int] | None = None,
        start_read_address: int = 0x00,
        read_count: int = 0,
    ) -> tuple[tuple[int, ...] | None, int]:
        """Execute a synchronous register write/read transaction.

        Args:
            start_write_address: First register address to write.
            values: Register values to write, or None if no write is requested
            start_read_address: First register address to read.
            read_count: Number of consecutive registers to read.

        Returns:
            A tuple containing:
                - hardware_values (tuple[int, ...] | None): Unpacked register values, or None if a fatal error occurs.
                - error_code (int): USB_NO_ERROR (0) on success, or a specific error code on fatal failure.
        """
        if not self.is_connected() or self._ser is None:
            return None, USB_NOT_CONNECTED
        packed_cmd, error = protocol.pack_command_transfer(
            start_write_address=start_write_address,
            values=values,
            start_read_address=start_read_address,
            read_count=read_count)
        if error != protocol.PROTOCOL_NO_ERROR or packed_cmd is None:
            return None, error
        expected_bytes = 1 + (2 * read_count)
        if expected_bytes > len(self._read_buffer):
            return None, USB_READ_BUFFER_OUT_OF_BOUNDS
        try:
            self._ser.write(packed_cmd)
        except (serial.SerialException, OSError):
            self.close()
            return None, USB_WRITE_ERROR
        try:
            bytes_read = self._ser.readinto(memoryview(self._read_buffer)[:expected_bytes])
            if bytes_read != expected_bytes:
                return None, USB_READ_ERROR
            return protocol.unpack_response_transfer(
                raw_bytes=bytes(self._read_buffer[:expected_bytes]),
                start_read_address=start_read_address,
                read_count=read_count)
        except (serial.SerialException, OSError):
            self.close()
            return None, USB_READ_ERROR