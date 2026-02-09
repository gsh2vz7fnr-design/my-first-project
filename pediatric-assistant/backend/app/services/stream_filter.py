"""
流式输出安全过滤器
"""
from typing import Optional
from loguru import logger

from app.models.user import StreamSafetyResult
from app.services.safety_filter import safety_filter


class StreamSafetyFilter:
    """流式输出安全过滤器"""

    def __init__(self):
        """初始化"""
        self.buffer: str = ""
        self.aborted: bool = False

    def check_chunk(self, chunk: str) -> StreamSafetyResult:
        """
        检查流式输出块是否包含违禁词

        Args:
            chunk: 当前输出块

        Returns:
            StreamSafetyResult: 检查结果
        """
        # 先检查（此时 buffer 不含当前 chunk）
        result = safety_filter.check_stream_output(chunk, self.buffer)

        # 再追加到buffer
        self.buffer += chunk

        # 如果需要中止，设置标志
        if result.should_abort:
            self.aborted = True

        return result

    def reset(self) -> None:
        """重置过滤器状态"""
        self.buffer = ""
        self.aborted = False
