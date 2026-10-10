import asyncio
import time
from typing import Optional, List, Callable, Dict, Any
from .models import Idea, ToolDecision
from .storage import storage
from .router import decision_router
from .tools.competitor_agent import competitor_agent
from .tools.workflow_agent import workflow_agent
from .tools.pros_cons_agent import pros_cons_agent
from .tools.summary_agent import summary_agent


class AgenticOrchestrator:
    """Coordinates asynchronous agentic tool execution, state updates,

    and atomic persistence for brainstorming ideas.
    """

    def __init__(self):
        self._listeners: List[Callable[[Dict[str, Any]], Any]] = []

    def subscribe(self, listener: Callable[[Dict[str, Any]], Any]):
        """Register a callback for real-time lifecycle updates (e.g. WebSockets)."""
        self._listeners.append(listener)

    async def _emit_event(self, event_type: str, data: Dict[str, Any]):
        for listener in self._listeners:
            try:
                res = listener({"event": event_type, "timestamp": time.time(), "data": data})
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                print(f"[Orchestrator] Error notifying listener: {e}")

    async def auto_evaluate_and_dispatch(
        self,
        identifier: str,
        context_delta: str,
        run_in_background: bool = True
    ) -> Dict[str, Any]:
        """Automatically evaluates whether new speech context warrants tool execution,

        and dispatches required agents.
        """
        idea = await storage.get_idea(identifier)
        if not idea:
            raise ValueError(f"Idea not found: '{identifier}'")

        # The idea record is the durable source of truth for the continuously
        # arriving transcript. Preserve each delta before dispatch decisions.
        clean_delta = context_delta.strip()
        if clean_delta:
            idea.transcript = "\n".join(filter(None, [idea.transcript, clean_delta]))
            idea.updated_at = time.time()
            await storage.save_or_update_idea(idea)

        # 1. Triage decision
        decision: ToolDecision = await decision_router.evaluate_context_delta(idea, context_delta)

        # Apply immediate delta updates if found (e.g. summary nuance, quick proponent/opponent notes)
        if decision.summary_refinement:
            idea.summary = decision.summary_refinement
        if decision.new_proponents:
            idea.proponents = list(dict.fromkeys(idea.proponents + decision.new_proponents))
        if decision.new_opponents:
            idea.opponents = list(dict.fromkeys(idea.opponents + decision.new_opponents))

        tools_to_run = []
        if decision.call_competitors:
            tools_to_run.append("competitors")
        if decision.call_workflow:
            tools_to_run.append("workflow")
        if decision.call_pros_cons:
            tools_to_run.append("pros_cons")

        if not tools_to_run:
            idea.updated_at = time.time()
            await storage.save_or_update_idea(idea)
            return {
                "idea_id": idea.id,
                "triggered": False,
                "message": "No agentic tools required for this context delta.",
                "tools": []
            }

        # Dispatch selected tools
        if run_in_background:
            asyncio.create_task(self._run_tool_pipeline(idea.id, tools_to_run, context_delta))
            return {
                "idea_id": idea.id,
                "triggered": True,
                "dispatched_tools": tools_to_run,
                "decision": decision.model_dump()
            }
        else:
            await self._run_tool_pipeline(idea.id, tools_to_run, context_delta)
            updated_idea = await storage.get_idea(idea.id)
            return {
                "idea_id": idea.id,
                "triggered": True,
                "dispatched_tools": tools_to_run,
                "idea": updated_idea.model_dump() if updated_idea else None
            }

    async def manual_dispatch(
        self,
        identifier: str,
        service: str,
        context: Optional[str] = None,
        run_in_background: bool = True
    ) -> Dict[str, Any]:
        """Enables the user to explicitly invoke a specific tool or 'all' services."""
        idea = await storage.get_idea(identifier)
        if not idea:
            raise ValueError(f"Idea not found: '{identifier}'")

        service_clean = service.lower().strip()
        if service_clean == "all":
            if run_in_background:
                asyncio.create_task(self.enrich_idea_from_transcript(idea.id, context))
                return {
                    "idea_id": idea.id,
                    "status": "enriching",
                    "dispatched_tools": ["summary", "pros_cons", "workflow", "competitors"],
                    "mode": "manual",
                }
            return await self.enrich_idea_from_transcript(idea.id, context)
        elif service_clean in ["competitors", "workflow", "pros_cons"]:
            tools_to_run = [service_clean]
        else:
            raise ValueError(f"Unknown service: '{service}'. Supported: competitors, workflow, pros_cons, all")

        full_context = context or idea.transcript or await storage.get_transcript()

        if run_in_background:
            asyncio.create_task(self._run_tool_pipeline(idea.id, tools_to_run, full_context))
            return {
                "idea_id": idea.id,
                "status": "enriching",
                "dispatched_tools": tools_to_run,
                "mode": "manual"
            }
        else:
            await self._run_tool_pipeline(idea.id, tools_to_run, full_context)
            updated_idea = await storage.get_idea(idea.id)
            return {
                "idea_id": idea.id,
                "status": "enriched",
                "dispatched_tools": tools_to_run,
                "idea": updated_idea.model_dump() if updated_idea else None
            }

    async def enrich_idea_from_transcript(
        self,
        identifier: str,
        transcript_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run the deterministic transcript -> insight -> design/research pipeline.

        Summary must finish first. Pros/cons then receives the complete source
        transcript, while workflow design and competitor discovery receive the
        distilled summary. Results are committed together to avoid subagent
        read/modify/write races in ideas.json.
        """
        idea = await storage.get_idea(identifier)
        if not idea:
            raise ValueError(f"Idea not found: '{identifier}'")

        transcript = (transcript_override or idea.transcript or "").strip()
        if not transcript:
            raise ValueError(
                f"Idea '{identifier}' has no transcript. Add `transcript` to its ideas.json record "
                "or provide it in the request body."
            )

        if transcript_override:
            idea.transcript = transcript
        idea.status = "enriching"
        idea.active_tools = ["summary"]
        idea.updated_at = time.time()
        await storage.save_or_update_idea(idea)
        await self._emit_event("tools_started", {
            "idea_id": idea.id,
            "tools": ["summary", "pros_cons", "workflow", "competitors"],
        })

        try:
            summary, key_takeaway = await summary_agent.run(idea, transcript)
            idea.summary = summary
            idea.metadata["key_takeaway"] = key_takeaway
            idea.active_tools = ["pros_cons", "workflow", "competitors"]

            pros_task = pros_cons_agent.run(idea, transcript)
            # These two intentionally use the concise summary, not the noisy
            # transcript, to produce a focused design and search query.
            workflow_task = workflow_agent.run(idea, summary)
            competitor_task = competitor_agent.run(idea, summary)
            results = await asyncio.gather(
                pros_task, workflow_task, competitor_task, return_exceptions=True
            )

            execution = {"summary": {"status": "success"}}
            failures = []

            pros_result, workflow_result, competitor_result = results
            if isinstance(pros_result, BaseException):
                failures.append("pros_cons")
                execution["pros_cons"] = {"status": "failed", "error": str(pros_result)}
            else:
                idea.pros_cons, idea.proponents, idea.opponents = pros_result
                execution["pros_cons"] = {"status": "success"}

            if isinstance(workflow_result, BaseException):
                failures.append("workflow")
                execution["workflow"] = {"status": "failed", "error": str(workflow_result)}
            else:
                idea.workflow = workflow_result
                execution["workflow"] = {"status": "success"}

            if isinstance(competitor_result, BaseException):
                failures.append("competitors")
                execution["competitors"] = {"status": "failed", "error": str(competitor_result)}
            else:
                idea.competitors = competitor_result
                execution["competitors"] = {"status": "success"}

            idea.status = "error" if failures else "enriched"
            idea.active_tools = []
            idea.updated_at = time.time()
            if failures:
                idea.metadata["enrichment_failures"] = failures
            else:
                idea.metadata.pop("enrichment_failures", None)
            await storage.save_or_update_idea(idea)
            await self._emit_event("idea_updated", {"idea": idea.model_dump()})
            return {
                "idea_id": idea.id,
                "status": idea.status,
                "execution": execution,
                "idea": idea.model_dump(),
            }
        except Exception:
            idea.status = "error"
            idea.active_tools = []
            idea.updated_at = time.time()
            await storage.save_or_update_idea(idea)
            raise

    async def _run_tool_pipeline(self, idea_id: str, tools: List[str], context: Optional[str]):
        """Executes selected tools concurrently and persists updates atomically."""
        idea = await storage.get_idea(idea_id)
        if not idea:
            return

        idea.status = "enriching"
        for t in tools:
            if t not in idea.active_tools:
                idea.active_tools.append(t)
        await storage.save_or_update_idea(idea)
        await self._emit_event("tools_started", {"idea_id": idea_id, "tools": tools})

        tasks = []
        for t in tools:
            if t == "competitors":
                tasks.append(self._run_competitor_subagent(idea_id, context))
            elif t == "workflow":
                tasks.append(self._run_workflow_subagent(idea_id, context))
            elif t == "pros_cons":
                tasks.append(self._run_pros_cons_subagent(idea_id, context))

        # Run subagents concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

        # Finalize idea state
        final_idea = await storage.get_idea(idea_id)
        if final_idea:
            final_idea.active_tools = [t for t in final_idea.active_tools if t not in tools]
            if not final_idea.active_tools:
                final_idea.status = "enriched"
            final_idea.updated_at = time.time()
            await storage.save_or_update_idea(final_idea)
            await self._emit_event("idea_updated", {"idea": final_idea.model_dump()})

    async def _run_competitor_subagent(self, idea_id: str, context: Optional[str]):
        try:
            idea = await storage.get_idea(idea_id)
            if not idea:
                return
            result = await competitor_agent.run(idea, context)
            
            # Re-fetch before saving to avoid race conditions with other subagents
            current_idea = await storage.get_idea(idea_id)
            if current_idea:
                current_idea.competitors = result
                current_idea.updated_at = time.time()
                await storage.save_or_update_idea(current_idea)
                await self._emit_event("tool_completed", {"idea_id": idea_id, "tool": "competitors", "result": result.model_dump()})
        except Exception as e:
            print(f"[Orchestrator] Error running competitor agent: {e}")

    async def _run_workflow_subagent(self, idea_id: str, context: Optional[str]):
        try:
            idea = await storage.get_idea(idea_id)
            if not idea:
                return
            result = await workflow_agent.run(idea, context)

            current_idea = await storage.get_idea(idea_id)
            if current_idea:
                current_idea.workflow = result
                # If thumbnail not set, can assign workflow image or placeholder
                if not current_idea.thumbnail and result.image_url:
                    current_idea.thumbnail = result.image_url
                current_idea.updated_at = time.time()
                await storage.save_or_update_idea(current_idea)
                await self._emit_event("tool_completed", {"idea_id": idea_id, "tool": "workflow", "result": result.model_dump()})
        except Exception as e:
            print(f"[Orchestrator] Error running workflow agent: {e}")

    async def _run_pros_cons_subagent(self, idea_id: str, context: Optional[str]):
        try:
            idea = await storage.get_idea(idea_id)
            if not idea:
                return
            result, updated_proponents, updated_opponents = await pros_cons_agent.run(idea, context)

            current_idea = await storage.get_idea(idea_id)
            if current_idea:
                current_idea.pros_cons = result
                current_idea.proponents = updated_proponents
                current_idea.opponents = updated_opponents
                current_idea.updated_at = time.time()
                await storage.save_or_update_idea(current_idea)
                await self._emit_event("tool_completed", {
                    "idea_id": idea_id,
                    "tool": "pros_cons",
                    "result": result.model_dump(),
                    "proponents": updated_proponents,
                    "opponents": updated_opponents
                })
        except Exception as e:
            print(f"[Orchestrator] Error running pros/cons agent: {e}")


orchestrator = AgenticOrchestrator()
