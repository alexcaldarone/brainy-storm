import json
import os
import re
import asyncio
import time
import httpx
from typing import Dict, Any, Optional, List
from .config import (
    DEFAULT_PROVIDER,
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    GEMINI_MODEL,
    OPENAI_MODEL,
)


class LLMClient:
    """Unified async client supporting Gemini (with Search Grounding), OpenAI, and Smart Mock mode."""

    def __init__(self):
        self.gemini_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        self.openai_key = OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
        self.http_client = httpx.AsyncClient(timeout=45.0)

    async def close(self):
        await self.http_client.aclose()

    async def search_web(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """Performs a live web search using DuckDuckGo API or HTML fallback."""
        results = []
        try:
            # DuckDuckGo Instant Answer API
            resp = await self.http_client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
                headers={"User-Agent": "Mozilla/5.0"}
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("AbstractText"):
                    results.append({
                        "title": data.get("Heading", query),
                        "snippet": data.get("AbstractText", ""),
                        "url": data.get("AbstractURL", "")
                    })
                for topic in data.get("RelatedTopics", [])[:num_results]:
                    if isinstance(topic, dict) and "Text" in topic:
                        results.append({
                            "title": topic.get("Text", "")[:60],
                            "snippet": topic.get("Text", ""),
                            "url": topic.get("FirstURL", "")
                        })
        except Exception:
            pass

        # If empty, try lite search
        if not results:
            try:
                lite_resp = await self.http_client.post(
                    "https://lite.duckduckgo.com/lite/",
                    data={"q": query},
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if lite_resp.status_code == 200:
                    text = lite_resp.text
                    snippets = re.findall(r'<td class="result-snippet">([^<]+)</td>', text)
                    for s in snippets[:num_results]:
                        clean = s.strip()
                        if clean:
                            results.append({"title": query, "snippet": clean, "url": ""})
            except Exception:
                pass

        return results

    async def generate_json(self, prompt: str, system_instruction: str = "", enable_search: bool = False) -> Dict[str, Any]:
        """Generates structured JSON using Gemini (preferred, with search grounding) or OpenAI."""
        provider = DEFAULT_PROVIDER.lower().strip()
        if provider == "mock":
            return self._generate_smart_mock(prompt, system_instruction)

        if provider in ("auto", "gemini") and self.gemini_key:
            try:
                return await self._call_gemini(prompt, system_instruction, enable_search=enable_search)
            except Exception as e:
                print(f"[LLMClient] Gemini error: {e}. Attempting fallback...")

        if provider in ("auto", "openai") and self.openai_key:
            try:
                return await self._call_openai(prompt, system_instruction)
            except Exception as e:
                print(f"[LLMClient] OpenAI error: {e}. Attempting fallback...")

        # If no valid API key or network error, return smart mock
        return self._generate_smart_mock(prompt, system_instruction)

    async def ping_models(self, provider: str = "all") -> Dict[str, Any]:
        """Make a minimal real request to configured providers.

        Unlike generation, this never falls back to mock mode, so it is safe to
        use as a credentials/model/connectivity diagnostic.
        """
        selected = provider.lower().strip()
        if selected not in {"all", "gemini", "openai"}:
            raise ValueError("provider must be one of: all, gemini, openai")

        providers = ["gemini", "openai"] if selected == "all" else [selected]
        checks = await asyncio.gather(*(self._ping_provider(name) for name in providers))
        return {
            "ok": all(check["status"] == "ok" for check in checks),
            "providers": {check["provider"]: check for check in checks},
        }

    async def _ping_provider(self, provider: str) -> Dict[str, Any]:
        model = GEMINI_MODEL if provider == "gemini" else OPENAI_MODEL
        key = self.gemini_key if provider == "gemini" else self.openai_key
        base = {"provider": provider, "model": model}
        if not key:
            return {**base, "status": "not_configured", "latency_ms": None}

        started = time.perf_counter()
        try:
            if provider == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                response = await self.http_client.post(
                    url,
                    headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": "Reply with exactly PONG"}]}],
                        "generationConfig": {"maxOutputTokens": 8, "temperature": 0},
                    },
                )
            else:
                response = await self.http_client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "Reply with exactly PONG"}],
                        "max_tokens": 8,
                        "temperature": 0,
                    },
                )
            response.raise_for_status()
            return {
                **base,
                "status": "ok",
                "latency_ms": round((time.perf_counter() - started) * 1000),
            }
        except httpx.HTTPStatusError as exc:
            return {
                **base,
                "status": "error",
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "http_status": exc.response.status_code,
                "error": "Provider rejected the ping request.",
            }
        except Exception as exc:
            return {
                **base,
                "status": "error",
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "error": f"{type(exc).__name__}: network request failed.",
            }

    async def _call_gemini(self, prompt: str, system_instruction: str, enable_search: bool = False) -> Dict[str, Any]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        
        body: Dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json"
            }
        }

        if system_instruction:
            body["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        # If search grounding is requested and model supports tools
        if enable_search:
            body["tools"] = [{"google_search": {}}]

        resp = await self.http_client.post(
            url,
            headers={"x-goog-api-key": self.gemini_key, "Content-Type": "application/json"},
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        
        # Extract text from response
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("No candidates returned by Gemini")
            
        text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
        # Parse JSON
        return json.loads(text_content)

    async def _call_openai(self, prompt: str, system_instruction: str) -> Dict[str, Any]:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json"
        }
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction + "\nReturn ONLY valid JSON."})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": OPENAI_MODEL,
            "messages": messages,
            "response_format": {"type": "json_object"}
        }

        resp = await self.http_client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)

    def _generate_smart_mock(self, prompt: str, system_instruction: str = "") -> Dict[str, Any]:
        """Provides realistic mock data when offline or keys are not provided."""
        lower_sys = system_instruction.lower()
        first_line = prompt.strip().split("\n")[0].lower()

        # 1. Competitor Agent
        if "competitive landscapes" in lower_sys or "competitor research ai agent" in first_line:
            return {
                "competitors": [
                    {
                        "name": "Miro / Mural",
                        "summary": "Collaborative digital whiteboards with AI clustering and templates.",
                        "differentiator": "Focuses on static post-it canvas rather than real-time voice-driven agentic tool calling."
                    },
                    {
                        "name": "Otter.ai / Fireflies",
                        "summary": "Meeting transcription and summary bots.",
                        "differentiator": "Only records transcripts and summaries, does not synthesize ideas or spawn autonomous subagents."
                    },
                    {
                        "name": "Whimsical AI",
                        "summary": "AI mind mapping and flowcharts generated from text prompts.",
                        "differentiator": "Requires manual prompt typing rather than continuous conversational transcription."
                    }
                ],
                "market_landscape": "The market is split between passive meeting recorders and static whiteboards. An active agentic brainstorming companion creates a distinct new category.",
                "our_positioning": "We position ourselves as an active AI co-founder during brainstorming: listening continuously, identifying distinct ideas, and autonomously dispatching research and workflow agents."
            }

        # 2. Workflow Agent
        if "senior software architect" in lower_sys or "visual workflow ai agent" in first_line:
            return {
                "summary": "Continuous voice capture feeds an idea extraction pipeline that triggers asynchronous agentic enrichment.",
                "steps": [
                    "User speaks in brainstorming session",
                    "Speech stream is transcribed in real-time",
                    "Engine detects and categorizes distinct ideas",
                    "Agentic router dispatches asynchronous tool calls (Competitors, Workflow, Pros/Cons)",
                    "Data is atomically persisted and live UI updates via WebSocket"
                ],
                "mermaid_code": "graph TD\n    A[Audio Input] --> B[Transcriber Microservice]\n    B --> C[Idea Engine]\n    C --> D{Agentic Router}\n    D -->|Web Research| E[Competitor Agent]\n    D -->|Process Mapping| F[Workflow Agent]\n    D -->|Debate Extraction| G[Pros & Cons Agent]\n    E --> H[Atomic ideas.json]\n    F --> H\n    G --> H\n    H --> I[Frontend Live Board]",
                "image_prompt": "Futuristic modern interactive brainstorming dashboard with floating agent cards, glowing data streams, sleek tech aesthetic"
            }

        # 3. Pros / Cons Agent
        if "product evaluator" in lower_sys or "critical debate" in first_line:
            return {
                "pros": [
                    "Eliminates manual note-taking and idea synthesis during fast-paced brainstorming",
                    "Real-time competitor grounding prevents teams from reinventing the wheel",
                    "Instant visual workflows accelerate shared team alignment"
                ],
                "cons": [
                    "Requires reliable low-latency speech transcription",
                    "Agentic tool calls can accumulate LLM token costs if not throttled",
                    "Potential hallucinations in competitor claims without search verification"
                ],
                "key_risks": [
                    "Microservice synchronization lag between transcriber and engine",
                    "Noise or cross-talk in room audio degrading idea extraction"
                ],
                "open_questions": [
                    "How often should the router re-evaluate updated idea context?",
                    "Should user manual clicks interrupt or queue behind background auto-evaluations?"
                ],
                "proponents": [
                    "Voice-first interface enables zero-friction ideation",
                    "Automatic agentic competitor check provides immediate reality testing"
                ],
                "opponents": [
                    "Concerned that spontaneous ideas might be prematurely rejected by competitor analysis",
                    "Need to verify privacy of recorded brainstorming sessions"
                ]
            }

        # 4. Decision / Triage Router
        if "agent dispatcher" in lower_sys or "agentic triage router" in first_line:
            return {
                "call_competitors": True,
                "competitor_reason": "Context discusses market alternatives and product category.",
                "call_workflow": True,
                "workflow_reason": "Context outlines key architecture and operational flow.",
                "call_pros_cons": True,
                "pros_cons_reason": "Context contains trade-off arguments and team feedback.",
                "summary_refinement": None,
                "new_proponents": ["Identified strong user demand in the discussion"],
                "new_opponents": ["Concerns raised regarding scalability and API rate limits"]
            }

        return {"status": "ok", "message": "Processed successfully"}


llm_client = LLMClient()
