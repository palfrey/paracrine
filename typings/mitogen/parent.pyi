from typing import Any, Callable, Optional, TypeVar

from mitogen.core import Error

T = TypeVar("T")

class Context:
    def call_async(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T: ...

class Router:
    def sudo(
        self,
        via: Optional[Context] = None,
        python_path: Optional[str] = None,
        preserve_env: Optional[bool] = None,
    ) -> Context: ...
    def ssh(self) -> Context: ...

class EofError(Error):
    pass
