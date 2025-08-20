from dataclasses import dataclass
from typing import List, Dict

@dataclass
class Source:
    title: str
    url: str
    snippet: str

@dataclass
class Answer:
    text: str
    sources: List[Source]

Message = Dict[str, str]  # {"role": "user"|"assistant", "content": str}
