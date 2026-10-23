"""Data shapes shared by the writer, guard, renderer and planner."""
from typing import List, Literal

from pydantic import BaseModel, Field

# Categories the guard treats specially (YouTube's July 2026 clarification:
# AI personas on health/finance topics are not monetizable).
Category = Literal["science", "history", "mystery", "language", "tech", "culture", "health", "finance", "other"]


class Beat(BaseModel):
    on_screen: str = Field(description="Short caption shown on screen, max ~12 words")
    narration: str = Field(description="What the voice says during this beat")


class Script(BaseModel):
    format: str = Field(description="The format id this script was written for")
    category: Category
    hook: str = Field(description="First 2 seconds: a line that stops the scroll")
    beats: List[Beat]
    perspective: str = Field(description="The channel's own take, opinion or test result that makes this video original")
    cta: str = Field(description="One-line call to action at the end")
    title: str = Field(description="YouTube title, under 70 characters, no clickbait lies")
    description: str
    tags: List[str]
    thumbnail_text: str = Field(description="2-5 words for the thumbnail")
    sources: List[str] = Field(description="Where the facts come from (names or URLs)")

    def narration_text(self) -> str:
        parts = [self.hook] + [b.narration for b in self.beats] + [self.perspective, self.cta]
        return " ".join(p.strip() for p in parts if p.strip())
