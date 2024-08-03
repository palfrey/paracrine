from typing import Any

class Error(Exception):
    pass

class StreamError(Error):
    pass

class Message:
    def unpickle(self) -> Any: ...

class Receiver:
    def get(self) -> Message: ...
