from beanie import Document
from typing import List


class PolicyChunk(Document):
    policy_name: str
    section: str
    content: str
    embedding: List[float]

    class Settings:
        name = "policy_chunks"
