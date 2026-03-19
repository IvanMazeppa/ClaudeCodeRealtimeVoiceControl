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
