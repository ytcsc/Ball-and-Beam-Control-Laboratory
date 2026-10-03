import struct

# Protocol communication headers
PROTOCOL_HEADER_WRITE_CMD = 0x57  # 'W'
PROTOCOL_HEADER_WRITE_RES = 0x77  # 'w'

# Protocol package formats
PROTOCOL_FMT_WRITE_CMD = "<BHh"
PROTOCOL_FMT_WRITE_RES = "<BB"

# Protocol packet sizes
PROTOCOL_SIZE_WRITE_CMD = struct.calcsize(PROTOCOL_FMT_WRITE_CMD)
PROTOCOL_SIZE_WRITE_RES = struct.calcsize(PROTOCOL_FMT_WRITE_RES)

# Error and warning codes
PROTOCOL_NO_ERROR = 0                           # No protocol error ocurred
PROTOCOL_ERROR_STEPS_OUT_OF_RANGE = 201         # Steps is outside the uint16 range
PROTOCOL_ERROR_SPEED_OUT_OF_RANGE = 202         # Speed is outside the int16 (signed) range
PROTOCOL_ERROR_INVALID_PACKET_LENGTH = 203      # Incoming packet has an invalid length

def pack_command_write(steps: int, speed: int) -> tuple[bytes | None, int]:
    """Pack a direct write command sent from the PC to the hardware.

    Packet structure (5 bytes):
        - header (uint8_t): Constant 'W' (0x57).
        - steps (uint16_t): Absolute number of steps for the stepper motor (direction is controlled by the sign of speed).
        - speed (int16_t): Speed in steps per second (the sign controls the direction).

    Args:
        steps (int): Absolute number of motor steps (0 to 65535).
        speed (int): Motor speed in steps per second (-32768 to 32767).

    Returns:
        tuple containing:
            - packed_command (bytes | None): bytes of the packed command, or None if a fatal error occurs.
            - error_code (int): PROTOCOL_NO_ERROR (0) on success, or a specific PROTOCOL_ERROR_* code on fatal failure.
    """
    if not 0 <= steps <= 65535:
        return None, PROTOCOL_ERROR_STEPS_OUT_OF_RANGE

    if not -32768 <= speed <= 32767:
        return None, PROTOCOL_ERROR_SPEED_OUT_OF_RANGE
    return struct.pack(PROTOCOL_FMT_WRITE_CMD, PROTOCOL_HEADER_WRITE_CMD, steps, speed), PROTOCOL_NO_ERROR

def unpack_response_write(raw_bytes: bytes) -> tuple[tuple[int, int] | None, int]:
    """Unpack the write confirmation response received from the hardware.

    Expected packet structure (2 bytes):
        - header (uint8_t): Constant 'w' (0x77).
        - ack (uint8_t): ACK/NACK response code.

    Args:
        raw_bytes (bytes): Binary buffer read from the serial port.

    Returns:
        tuple containing:
            - unpacled_values (tuple[int, int] | None): tuple containing (header, ack), or None if a fatal error occurs.
            - error_code (int): PROTOCOL_NO_ERROR (0) on success, or a specific PROTOCOL_ERROR_* code on fatal failure.
    """
    if len(raw_bytes) != PROTOCOL_SIZE_WRITE_RES:
        return None, PROTOCOL_ERROR_INVALID_PACKET_LENGTH
    return struct.unpack(PROTOCOL_FMT_WRITE_RES, raw_bytes), PROTOCOL_NO_ERROR