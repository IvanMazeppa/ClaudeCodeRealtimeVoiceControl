from __future__ import annotations

from pydantic import BaseModel, Field


class MentorSummary(BaseModel):
    spoken_response: str
    screen_summary: str
    bullets: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommended_next_step: str | None = None


class ChangeExplanation(MentorSummary):
    changed_files: list[str] = Field(default_factory=list)


class SecondOpinion(MentorSummary):
    verdict: str | None = None
    drafted_follow_up_prompt: str | None = None


class ClaudePromptDraft(MentorSummary):
    drafted_prompt: str


class ApprovalExplanation(MentorSummary):
    approval_recommendation: str | None = None
    approval_reason: str | None = None


class RoadmapItem(BaseModel):
    title: str
    priority: str = Field(description="high, medium, or low")
    description: str
    rationale: str = Field(description="Key reasoning from the GPT+Opus discussion")
    estimated_complexity: str = Field(
        default="unknown",
        description="small, medium, large, or unknown",
    )


class CollaborativeRoadmap(BaseModel):
    spoken_summary: str = Field(description="1-2 sentence voice summary for the user")
    executive_summary: str = Field(description="2-3 paragraph overview of findings")
    items: list[RoadmapItem] = Field(default_factory=list)
    conversation_highlights: list[str] = Field(
        default_factory=list,
        description="Notable insights or disagreements from the GPT↔Opus exchanges",
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Unresolved questions that need human input",
    )
