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
        search_results = (
            []
            if DEFAULT_PROVIDER.lower() == "mock"
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
  "our_positioning": "How our idea stands out and positions against these competitors"
}}
"""

        system_instruction = "You are an expert startup analyst specializing in competitive landscapes and strategic positioning. Always respond in valid JSON."

        # Enable Gemini search grounding if Gemini is active
        raw_output = await llm_client.generate_json(
            prompt=prompt,
            system_instruction=system_instruction,
            enable_search=True
        )

        competitors = []
        for c in raw_output.get("competitors", []):
            if isinstance(c, dict) and "name" in c:
                competitors.append(CompetitorItem(
                    name=c.get("name", "Unknown"),
                    summary=c.get("summary", ""),
                    differentiator=c.get("differentiator", ""),
                    idea=c.get("idea"),
                    yearOfFounding=c.get("yearOfFounding"),
                    shortBio=c.get("shortBio"),
                    howWeDiffer=c.get("howWeDiffer"),
                ))

        enrichment = CompetitorEnrichment(
            competitors=competitors,
            market_landscape=raw_output.get("market_landscape", ""),
            our_positioning=raw_output.get("our_positioning", ""),
            groundingSources=[
                r.get("url", "") for r in search_results if r.get("url")
            ],
        )

        print(f"[CompetitorAgent] Completed for '{idea.title}' with {len(competitors)} competitors found.")
        return enrichment


competitor_agent = CompetitorAgent()
