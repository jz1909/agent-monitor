class ToolBackend:

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def specs(self) -> list[dict]:
        return []

    async def call(self, name: str, arguments: str) -> str:
        return f"unknown tool: {name}"

    def extras(self) -> dict:
        return {}
