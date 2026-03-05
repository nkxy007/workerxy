from dataclasses import dataclass, asdict
from typing import Optional
import json

@dataclass
class AgentMessage:
    content: str          # the text of the message
    author: str           # who sent it
    channel_id: Optional[int] = None   # Discord channel ID
    channel_name: Optional[str] = None # Discord channel name (e.g. "Network-jobs")
    guild_id: Optional[int] = None
    message_id: Optional[str] = None  # for correlation/auditing

    def to_json(self) -> bytes:
        return json.dumps(asdict(self)).encode()

    @classmethod
    def from_json(cls, data: bytes) -> "AgentMessage":
        return cls(**json.loads(data))
