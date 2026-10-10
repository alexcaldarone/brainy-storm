import json
from typing import Optional
from ..models import Idea, CompetitorEnrichment, CompetitorItem
from ..llm_client import llm_client
from ..config import DEFAULT_PROVIDER


class CompetitorAgent:
    """Subagent responsible for discovering competitors, analyzing their ideas,

    and generating strategic positioning for our idea.
    """

    async def run(self, idea: Idea, context: Optional[str] = None) -> CompetitorEnrichment:
        print(f"[CompetitorAgent] Running for idea: '{idea.title}'")

        # 1. Gather web search context if possible
        search_query = f"{idea.title} {idea.summary[:80]} competitors alternatives"
        provider = DEFAULT_PROVIDER.lower()
        uses_gemini_grounding = provider == "gemini" or (
            provider == "auto" and bool(llm_client.gemini_key)
        )
        # Keep an independent web-search fallback even when Gemini grounding is
        # enabled. Some model/search combinations can return no candidates; the
        # same prompt can then retry without the tool while retaining sources.
        search_results = (
            []
            if provider == "mock"
            else await llm_client.search_web(search_query, num_results=4)
        )

        search_context_str = ""
        if search_results:
            search_context_str = "\n".join(
                [f"- {r.get('title')}: {r.get('snippet')} ({r.get('url')})" for r in search_results]
            )

        # 2. Construct LLM prompt
        prompt = f"""
You are a Market Intelligence & Competitor Research AI Agent for a brainstorming session.

IDEA DETAILS:
- Title: {idea.title}
- Summary: {idea.summary}
- Proponents: {', '.join(idea.proponents) if idea.proponents else 'None specified'}
- Opponents: {', '.join(idea.opponents) if idea.opponents else 'None specified'}

CONVERSATION / TRANSCRIPT CONTEXT:
{context or 'No additional transcript context provided.'}

WEB SEARCH DISCOVERIES:
{search_context_str or 'No external web search results found.'}

TASK:
1. Identify 2 to 4 real existing competitors, similar companies, open-source projects, or legacy approaches.
2. For each, provide its product idea, founding year when verifiable, a short bio, and how our idea differs.
3. Formulate the general market landscape.
4. Define explicitly HOW WE POSITION OURSELVES TOWARDS THEM (our unique value proposition, advantages, or different angle).

Return your response in pure JSON format matching this schema:
{{
  "summary": "Concise conclusion from the competitor research",
  "competitors": [
    {{
      "name": "Competitor Name",
      "summary": "What they do and their core offering",
      "differentiator": "Their focus or how they solve it",
      "idea": "Their core product idea",
      "yearOfFounding": "YYYY or Unknown",
      "shortBio": "One-sentence factual company/product bio",
      "howWeDiffer": "Specific difference versus our summarized idea"
    }}
  ],
  "market_landscape": "Brief synthesis of current solutions in the market",
  "our_positioning": "How our idea stands out and positions against these competitors",
  "groundingSources": ["https://source-used.example/page"]
}}
"""

        system_instruction = "You are an expert startup analyst specializing in competitive landscapes and strategic positioning. Always respond in valid JSON."

        # Enable Gemini search grounding if Gemini is active
        raw_output = await llm_client.generate_json(
            prompt=prompt,
            system_instruction=system_instruction,
            enable_search=uses_gemini_grounding
        )

        competitors = []
        raw_competitors = raw_output.get("competitors")
        if not isinstance(raw_competitors, list):
            raw_competitors = []
        for c in raw_competitors:
            if isinstance(c, dict) and "name" in c:
                summary = str(c.get("summary") or "Not provided")
                differentiator = str(c.get("differentiator") or "Not provided")
                competitors.append(CompetitorItem(
                    name=str(c.get("name") or "Unknown"),
                    summary=summary,
                    differentiator=differentiator,
                    idea=str(c.get("idea") or summary),
                    yearOfFounding=str(c.get("yearOfFounding") or "Unknown"),
                    shortBio=str(c.get("shortBio") or summary),
                    howWeDiffer=str(c.get("howWeDiffer") or differentiator),
                ))

        discovered_sources = [
            r.get("url", "") for r in search_results if r.get("url")
        ]
        raw_model_sources = raw_output.get("groundingSources")
        if not isinstance(raw_model_sources, list):
            raw_model_sources = []
        model_sources = []
        for source in raw_model_sources:
            url = source.get("url") if isinstance(source, dict) else source
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                model_sources.append(url)
        grounding_sources = list(dict.fromkeys(discovered_sources + model_sources))

        enrichment = CompetitorEnrichment(
            summary=str(raw_output.get("summary") or raw_output.get("market_landscape") or "Not provided"),
            competitors=competitors,
            market_landscape=str(raw_output.get("market_landscape") or "Not provided"),
            our_positioning=str(raw_output.get("our_positioning") or "Not provided"),
            groundingSources=grounding_sources,
        )

        print(f"[CompetitorAgent] Completed for '{idea.title}' with {len(competitors)} competitors found.")
        return enrichment


competitor_agent = CompetitorAgent()
