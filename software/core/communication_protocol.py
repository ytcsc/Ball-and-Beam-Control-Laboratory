import struct

from .message_handler import MessageHandler
from .usb_manager import USBManager

class CommunicationProtocol:
    """High-level protocol parser and transaction coordinator over USBManager."""

    # Protocol communication headers
    PROTOCOL_HEADER_TRANSFER_CMD = 0x54  # 'T'
    PROTOCOL_HEADER_TRANSFER_RES = 0x74  # 't'

    # Protocol packet static formats
    PROTOCOL_FMT_TRANSFER_CMD = "<BBBBB"    # Header ('T'), start write address (uint8), write count (uint8), start read address (uint8), read count (uint8)

    # Register formats
    PROTOCOL_REGISTER_FORMATS = {
        0x00: "H",  # hardware status (uint16)
        0x01: "H",  # motor steps (uint16)
        0x02: "h",  # motor speed (int16)
        0x03: "H",  # set point (uint16)
        0x04: "h",  # X acceleration (int16)
        0x05: "h",  # Y acceleration (int16)
        0x06: "h",  # Z acceleration (int16)
        0x07: "h",  # X gyroscope (int16)
        0x08: "h",  # Y gyroscope (int16)
        0x09: "h",  # Z gyroscope (int16)
        0x0A: "H",  # hall encoder (uint16)
        0x0B: "H",  # linear sensor 1 (uint16)
        0x0C: "H",  # linear sensor 2 (uint16)
        0x0D: "H",  # potentiometer 1 (uint16)
        0x0E: "H",  # potentiometer 2 (uint16)
        0x0F: "H",  # potentiometer 3 (uint16)
    }
    PROTOCOL_MAX_REGISTER_ADDR = max(PROTOCOL_REGISTER_FORMATS.keys())

    # Error and warning codes
    PROTOCOL_ERROR_WCOUNT_OUT_OF_BOUNDS = 201       # Write operation address is out of bounds
    PROTOCOL_ERROR_RCOUNT_OUT_OF_BOUNDS = 202       # Read operation address is out of bounds
    PROTOCOL_ERROR_INVALID_PACKET_LENGTH = 203      # Incoming packet has an invalid length
    PROTOCOL_ERROR_INVALID_ADDRESS = 204            # Invalid starting address for read/write operation
    PROTOCOL_ERROR_VALUE_OUT_OF_RANGE = 205         # Write value is out of the register range
    PROTOCOL_ERROR_INVALID_HEADER = 206             # Hardware returned incorrect header

    def __init__(self) -> None:
         """Initialize the protocol handler."""
         self.usb: USBManager = USBManager()
         self.msg_handler: MessageHandler = MessageHandler()

    def _pack_command_transfer(self, start_write_address: int = 0x00, values: list[int] | None = None, start_read_address: int = 0x00, read_count: int = 0) -> bytes | None:
        """Pack the sequential transfer command sent from PC to hardware.

        Packet structure:
            - header (uint8_t): Constant 'T' (0x54).
            - start_write_address (uint8_t): Initial register address for the write operation.
            - write_count (uint8_t): Number of consecutive registers to write.
            - start_read_address (uint8_t): Initial register address for the read operation.
            - read_count (uint8_t): Number of consecutive registers to read.
            - values: Register values encoded according to PROTOCOL_REGISTER_FORMATS.

        Args:
            start_write_address (int): Initial register address for the write operation.
            values (list[int] | None): Values to write to consecutive registers. The number of values determines the write count.
            start_read_address (int): Initial register address for the read operation.
            read_count (int): Number of consecutive registers to read.

        Returns:
            packed_command (bytes | None): Packed transfer command, or None if a fatal error occurs.
        """
        if values is None:
            values = []
        write_count = len(values)
        if not (0 <= start_write_address <= self.PROTOCOL_MAX_REGISTER_ADDR):
            self.msg_handler.add_msg(self.PROTOCOL_ERROR_INVALID_ADDRESS)
            return None
        if not (0 <= start_read_address <= self.PROTOCOL_MAX_REGISTER_ADDR):
            self.msg_handler.add_msg(self.PROTOCOL_ERROR_INVALID_ADDRESS)
            return None
        if read_count < 0:
            self.msg_handler.add_msg(self.PROTOCOL_ERROR_RCOUNT_OUT_OF_BOUNDS)
            return None
        if (write_count > 0) and (start_write_address + len(values) - 1) > self.PROTOCOL_MAX_REGISTER_ADDR:
            self.msg_handler.add_msg(self.PROTOCOL_ERROR_WCOUNT_OUT_OF_BOUNDS)
            return None
        if (read_count > 0) and (start_read_address + read_count - 1) > self.PROTOCOL_MAX_REGISTER_ADDR:
            self.msg_handler.add_msg(self.PROTOCOL_ERROR_RCOUNT_OUT_OF_BOUNDS)
            return None
        fmt = self.PROTOCOL_FMT_TRANSFER_CMD
        for i, value in enumerate(values):
            address = start_write_address + i
            if self.PROTOCOL_REGISTER_FORMATS[address] == "h":
                if not -32768 <= value <= 32767:
                    self.msg_handler.add_msg(self.PROTOCOL_ERROR_VALUE_OUT_OF_RANGE)
                    return None
            elif self.PROTOCOL_REGISTER_FORMATS[address] == "H":
                if not 0 <= value <= 65535:
                    self.msg_handler.add_msg(self.PROTOCOL_ERROR_VALUE_OUT_OF_RANGE)
                    return None
            fmt += self.PROTOCOL_REGISTER_FORMATS[address]
        return struct.pack(
            fmt,
            self.PROTOCOL_HEADER_TRANSFER_CMD,
            start_write_address,
            write_count,
            start_read_address,
            read_count,
            *values)

    def _unpack_response_transfer(self, raw_bytes: bytes, start_read_address: int = 0x00, read_count: int = 0) -> tuple[int, ...] | None:
        """Unpack the sequential transfer response received from hardware.

        Packet structure:
            - header (uint8_t): Constant 't' (0x74).
            - register_values: Values encoded according to PROTOCOL_REGISTER_FORMATS.

        Args:
            raw_bytes (bytes): Binary buffer received from the hardware.
            start_read_address (int): Initial register address requested.
            read_count (int): Number of consecutive registers requested.

        Returns:
            hardware_values (tuple[int, ...] | None): Unpacked register values, or None if a fatal error occurs.
        """
        if not (0 <= start_read_address <= self.PROTOCOL_MAX_REGISTER_ADDR):
            self.msg_handler.add_msg(self.PROTOCOL_ERROR_INVALID_ADDRESS)
            return None
        if not (0 <= read_count):
            self.msg_handler.add_msg(self.PROTOCOL_ERROR_RCOUNT_OUT_OF_BOUNDS)
            return None
        if (read_count > 0) and (start_read_address + read_count - 1) > self.PROTOCOL_MAX_REGISTER_ADDR:
            self.msg_handler.add_msg(self.PROTOCOL_ERROR_RCOUNT_OUT_OF_BOUNDS)
            return None
        expected_length = 1 + 2 * read_count
        if len(raw_bytes) != expected_length:
            self.msg_handler.add_msg(self.PROTOCOL_ERROR_INVALID_PACKET_LENGTH)
            return None
        if raw_bytes[0] != self.PROTOCOL_HEADER_TRANSFER_RES:
            self.msg_handler.add_msg(self.PROTOCOL_ERROR_INVALID_HEADER)
            return None
        fmt = "<"
        for i in range(read_count):
            address = start_read_address + i
            fmt += self.PROTOCOL_REGISTER_FORMATS[address]
        return struct.unpack(fmt, raw_bytes[1:])

    def transfer(self, start_write_address: int = 0x00, values: list[int] | None = None, start_read_address: int = 0x00, read_count: int = 0) -> tuple[int, ...] | None:
            """Execute a synchronous register write/read transaction.

            Args:
                start_write_address (int): First register address to write.
                values (list[int] | None): Register values to write, or None
                    if no write is requested
                start_read_address (int): First register address to read.
                read_count (int): Number of consecutive registers to read.

            Returns:
                hardware_values (tuple[int, ...] | None): Unpacked register
                values, or None if a fatal error occurs.
            """
            if not self.usb.is_connected():
                self.msg_handler.add_msg(self.usb.USB_NOT_CONNECTED)
                return None
            
            packed_cmd = self._pack_command_transfer(
                start_write_address=start_write_address,
                values=values,
                start_read_address=start_read_address,
                read_count=read_count)

            if self.msg_handler.has_errors() or packed_cmd is None:
                return None
            
            expected_bytes = 1 + (2 * read_count)
            self.usb.write(packed_cmd)
            while self.usb.msg_handler.has_msgs():
                self.msg_handler.add_msg(self.usb.msg_handler.pop_msg())

            if self.msg_handler.has_errors():
                return None

            bytes_read = self.usb.read(expected_bytes=expected_bytes)
            while self.usb.msg_handler.has_msgs():
                self.msg_handler.add_msg(self.usb.msg_handler.pop_msg())

            if self.msg_handler.has_errors() or bytes_read is None:
                return None
            
            unpacked_msg = self._unpack_response_transfer(
                raw_bytes=bytes_read,
                start_read_address=start_read_address,
                read_count=read_count)
            if self.msg_handler.has_errors() or unpacked_msg is None:
                return None
            
            return unpacked_msg