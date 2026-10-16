class MessageHandler:
    """Manages non-blocking messages.

    This class provides a queue to store numeric error or warning codes
    passed between system modules.

    Attributes:
        max_msgs (int): Maximum number of message codes stored simultaneously.
    """
    def __init__(self, max_msgs: int = 20) -> None:
        """Initializes the MessageHandler instance.

        Args:
            max_msgs (int, optional): Maximum capacity of the message queue.
                Defaults to 20.
        """
        self.max_msgs: int = max_msgs
        self._msgs: list[int] = []

    def add_msg(self, code: int) -> None:
        """Appends a message code to the queue if capacity has not been
        reached.

        Args:
            code (int): Numeric message or warning code to append.
        """
        if len(self._msgs) < self.max_msgs:
            self._msgs.append(code)

    def pop_msg(self) -> int | None:
        """Removes and returns the oldest message code from the queue (FIFO).

        Returns:
            int | None: The oldest numeric code in the queue, or None if empty.
        """
        if self.has_msgs():
            return self._msgs.pop(0)
        return None

    def has_msgs(self) -> bool:
        """Checks whether there are any pending messages in the queue.

        Returns:
            bool: True if there is at least one message, False otherwise.
        """
        return len(self._msgs) > 0

    def clear_msgs(self) -> None:
        """Removes all messages from the queue."""
        self._msgs.clear()