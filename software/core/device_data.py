import time

from .message_handler import MessageHandler
from .communication_protocol import CommunicationProtocol


class DeviceData:
    """Manages physical domain values and handles hardware synchronization.

    Converts binary register units into human-readable physical quantities
    (e.g., degrees, g-force, deg/s, cm) and maintains timestamp records of the
    last successful communication.
    """

    # Hardware conversion factors
    STEPPER_DEGREES_PER_STEP = 1.4000
    SENSOR_ACCEL_SENSITIVITY_PER_G = 16384.0
    SENSOR_GYRO_SENSITIVITY_PER_DEG_PER_S = 131.0
    SENSOR_HALL_SENSITIVITY_PER_DEG = 2.8444
    SENSOR_LINEAR_1_SENSITIVITY_PER_CM = 1024.0
    SENSOR_LINEAR_2_SENSITIVITY_PER_CM = 1024.0
    SENSOR_POT_RESOLUTION = 1024.0

    def __init__(self) -> None:
        """Initialize device data."""
        self.protocol: CommunicationProtocol = CommunicationProtocol()
        self.msg_handler: MessageHandler = MessageHandler()
        self.motor_steps: int = 0               # In steps
        self.motor_speed: int = 0               # In steps per second
        self.setpoint: int = 0                  # Integer value of setpoint (50 cm = 65535)
        self.accel_x: float = 0.0               # In g's
        self.accel_y: float = 0.0               # In g's
        self.accel_z: float = 0.0               # In g's
        self.gyro_x: float = 0.0                # In degrees per second
        self.gyro_y: float = 0.0                # In degrees per second
        self.gyro_z: float = 0.0                # In degrees per second
        self.hall: float = 0.0                  # In degrees
        self.linear_1: float = 0.0              # In centimeters
        self.linear_2: float = 0.0              # In centimeters
        self.pot_1: float = 0.0                 # In percentage [0, 1]
        self.pot_2: float = 0.0                 # In percentage [0, 1]
        self.pot_3: float = 0.0                 # In percentage [0, 1]
        self.last_update: float | None = None   # In seconds

    def connect(self) -> bool:
        """Establish connection with the hardware interface.

        Attempts to connect via USB interface through the protocol layer and
        transfers any resulting messages or errors to the local message handler.

        Returns:
            bool: True if connection was successfully established, False otherwise.
        """
        flag = self.protocol.usb.connect()
        while self.protocol.usb.msg_handler.has_msgs():
            self.msg_handler.add_msg(self.protocol.usb.msg_handler.pop_msg())
        return flag

    def disconnect(self) -> None:
        """Safely close the USB port."""
        self.protocol.usb.close()
        while self.protocol.usb.msg_handler.has_msgs():
            self.msg_handler.add_msg(self.protocol.usb.msg_handler.pop_msg())

    def set_motor_values(self, angle: float, speed: float, setpoint: float = 0.0) -> None:
        """Convert physical motor values (degs and deg/s) to register values.

        Args:
            angle (float): Desired motor step in degrees.
            speed (float): Desired motor speed in degrees per second.
            setpoint (float): Target setpoint in centimeters (scaled 0-50 cm).
        """
        self.motor_steps = round(angle / self.STEPPER_DEGREES_PER_STEP)
        if self.motor_steps > 65535:
            self.motor_steps = 65535
        elif self.motor_steps < 0:
            self.motor_steps = 0

        self.motor_speed = round(speed / self.STEPPER_DEGREES_PER_STEP)
        if self.motor_speed > 32767:
            self.motor_speed = 32767
        elif self.motor_speed < -32768:
            self.motor_speed = -32768

        self.setpoint = round(65535 * (setpoint / 50.0))
        if self.setpoint > 65535:
            self.setpoint = 65535
        elif self.setpoint < 0:
            self.setpoint = 0

    def update_device_values(self) -> None:
        """Perform a synchronous transfer transaction and update physical
        sensor readings.

        Transmits configured motor/setpoint register values to the hardware,
        reads raw sensor data registers back, and converts binary readings
        into physical units if no fatal protocol or communication errors occur.
        """
        values = [self.motor_steps, self.motor_speed, self.setpoint]
        data = self.protocol.transfer(start_write_address=0x01, values=values, start_read_address=0x04, read_count=12)
        while self.protocol.msg_handler.has_msgs():
            self.msg_handler.add_msg(self.protocol.msg_handler.pop_msg())
        if self.msg_handler.has_errors() or data is None:
            return
        self.last_update = time.perf_counter()
        self.accel_x = data[0] / self.SENSOR_ACCEL_SENSITIVITY_PER_G
        self.accel_y = data[1] / self.SENSOR_ACCEL_SENSITIVITY_PER_G
        self.accel_z = data[2] / self.SENSOR_ACCEL_SENSITIVITY_PER_G
        self.gyro_x = data[3] / self.SENSOR_GYRO_SENSITIVITY_PER_DEG_PER_S
        self.gyro_y = data[4] / self.SENSOR_GYRO_SENSITIVITY_PER_DEG_PER_S
        self.gyro_z = data[5] / self.SENSOR_GYRO_SENSITIVITY_PER_DEG_PER_S
        self.hall = data[6] / self.SENSOR_HALL_SENSITIVITY_PER_DEG
        self.linear_1 = data[7] / self.SENSOR_LINEAR_1_SENSITIVITY_PER_CM
        self.linear_2 = data[8] / self.SENSOR_LINEAR_2_SENSITIVITY_PER_CM
        self.pot_1 = data[9] / self.SENSOR_POT_RESOLUTION
        self.pot_2 = data[10] / self.SENSOR_POT_RESOLUTION
        self.pot_3 = data[11] / self.SENSOR_POT_RESOLUTION
