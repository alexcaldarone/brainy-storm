from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator
import uuid
import time


class CompetitorItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = "Unknown"
    summary: str = ""
    differentiator: str = ""  # How they differ or what their unique angle is
    idea: Optional[str] = None
    yearOfFounding: Optional[str] = None
    shortBio: Optional[str] = None
    howWeDiffer: Optional[str] = None


class CompetitorEnrichment(BaseModel):
    model_config = ConfigDict(extra="allow")
    summary: Optional[str] = None
    competitors: List[CompetitorItem] = Field(default_factory=list)
    market_landscape: str = ""
    our_positioning: str = ""  # How we position ourselves against them
    groundingSources: Optional[List[str]] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


class WorkflowEnrichment(BaseModel):
    model_config = ConfigDict(extra="allow")
    summary: str = ""
    steps: List[str] = Field(default_factory=list)
    mermaid_code: Optional[str] = ""  # Mermaid.js diagram (flowchart or sequence)
    mermaidCode: Optional[str] = None
    image_prompt: str = ""  # Ready-to-use prompt for image generation
    image_url: Optional[str] = None  # URL or local path to generated thumbnail/diagram
    generated_at: float = Field(default_factory=time.time)


class ProsConsEnrichment(BaseModel):
    model_config = ConfigDict(extra="allow")
    summary: Optional[str] = None
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    key_risks: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


class Idea(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    summary: str = ""
    transcript: Optional[str] = None
    raw_body: str = Field(
        default="",
        description="Cumulative transcript excerpts relevant to this idea; canonical enrichment context",
    )
    proponents: List[str] = Field(
        default_factory=list,
        description="Who supports the idea or arguments in favor"
    )
    opponents: List[str] = Field(
        default_factory=list,
        description="Who opposes the idea or arguments against"
    )
    thumbnail: Optional[str] = None

    # Agentic Tool Enriched Outputs
    competitors: Optional[CompetitorEnrichment] = None
    workflow: Optional[WorkflowEnrichment] = None
    pros_cons: Optional[ProsConsEnrichment] = None
    systemGraph: Optional[Dict[str, Any]] = None

    # Execution State
    status: Literal["idle", "enriching", "enriched", "error"] = "idle"
    active_tools: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def backfill_raw_body_for_legacy_records(self):
        if not self.raw_body and self.transcript:
            self.raw_body = self.transcript
        return self


class ToolDecision(BaseModel):
    """Output from the Decision Router analyzing context delta."""
    call_competitors: bool = False
    competitor_reason: Optional[str] = None
    call_workflow: bool = False
    workflow_reason: Optional[str] = None
    call_pros_cons: bool = False
    pros_cons_reason: Optional[str] = None
    summary_refinement: Optional[str] = None
    new_proponents: List[str] = Field(default_factory=list)
    new_opponents: List[str] = Field(default_factory=list)


# API Request/Response DTOs
class AutoEnrichRequest(BaseModel):
    idea_id: Optional[str] = None
    title: Optional[str] = None
    context: str = Field(..., description="Newly transcribed speech or discussion context")


class ManualEnrichRequest(BaseModel):
    idea_id: Optional[str] = None
    title: Optional[str] = None
    service: Literal["competitors", "workflow", "pros_cons", "all"] = Field(
        ...,
        description="Service/tool to run: 'competitors', 'workflow', 'pros_cons', or 'all'"
    )
    context: Optional[str] = Field(default=None, description="Optional extra context")


class IdeaCreateUpdateRequest(BaseModel):
    id: Optional[str] = None
    title: str
    summary: Optional[str] = None
    transcript: Optional[str] = None
    raw_body: Optional[str] = None
    proponents: List[str] = Field(default_factory=list)
    opponents: List[str] = Field(default_factory=list)
    thumbnail: Optional[str] = None


class TranscriptEnrichRequest(BaseModel):
    """Optional transcript override for one enrichment run.

    When omitted, the selected idea's `transcript` field in ideas.json is used.
    The override is persisted so later refreshes use the same source text.
    """

    transcript: Optional[str] = None


class IdeaIngestRequest(BaseModel):
    title: Optional[str] = None
    transcript: str = Field(
        min_length=1,
        description="New full-session transcript or transcript delta to filter for this idea",
    )
    enrich: bool = True
