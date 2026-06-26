"""数据模型：Transcript、TranscriptSegment、ReadingGuide。"""

from .transcript import Transcript, TranscriptSegment, SourceType
from .guide import ReadingGuide

__all__ = ["Transcript", "TranscriptSegment", "SourceType", "ReadingGuide"]
