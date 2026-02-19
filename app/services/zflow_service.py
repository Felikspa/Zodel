from __future__ import annotations

from typing import Generator, Optional

from app.helper import get_embeddings, stream_chat
from app.zflow_runner import ZflowRunner


class ZflowService:
    def execute(self, script: str) -> Generator[str, None, None]:
        runner = ZflowRunner(stream_callback=stream_chat, embedding_callback=get_embeddings)
        yield from runner.execute_stream(code=script)

