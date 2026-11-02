"""Provider-independent, sanitized AI failure codes."""


class AIError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)
