from typing import Optional, Tuple, List
from ..models import Idea, ProsConsEnrichment
from ..llm_client import llm_client


class ProsConsAgent:
    """Subagent responsible for critical analysis, extracting pros and cons,

    identifying risks, and categorizing proponents and opponents from discussions.
    """

    async def run(self, idea: Idea, context: Optional[str] = None) -> Tuple[ProsConsEnrichment, List[str], List[str]]:
        print(f"[ProsConsAgent] Running for idea: '{idea.title}'")

        prompt = f"""
You are a Critical Debate & Evaluation AI Agent for a brainstorming session.

IDEA DETAILS:
- Title: {idea.title}
- Summary: {idea.summary}
- Existing Proponents: {', '.join(idea.proponents) if idea.proponents else 'None'}
- Existing Opponents: {', '.join(idea.opponents) if idea.opponents else 'None'}

TRANSCRIPT / DISCUSSION CONTEXT:
{context or 'No additional transcript context provided.'}

TASK:
1. Identify 2 to 4 key PROS (strengths, advantages, high-impact value).
2. Identify 2 to 4 key CONS (drawbacks, implementation hurdles, friction).
3. Identify major RISKS (technical, market, or operational).
4. Identify OPEN QUESTIONS that the brainstorming team should resolve.
5. Extract or refine PROPONENTS: specific stakeholders, team members, or arguments strongly in favor.
6. Extract or refine OPPONENTS: specific stakeholders, team members, or arguments critical/opposed.

Return your response in pure JSON format matching this schema:
{{
  "pros": ["Pro 1...", "Pro 2..."],
  "cons": ["Con 1...", "Con 2..."],
  "key_risks": ["Risk 1...", "Risk 2..."],
  "open_questions": ["Question 1...", "Question 2..."],
  "proponents": ["Proponent argument or persona 1", "Proponent argument 2"],
  "opponents": ["Opponent argument or critic 1", "Opponent argument 2"]
}}
"""

        system_instruction = "You are a pragmatic, analytical product evaluator. You cut through hype to find real pros, cons, and risks. Always respond in valid JSON."

        raw_output = await llm_client.generate_json(
            prompt=prompt,
            system_instruction=system_instruction
        )

        enrichment = ProsConsEnrichment(
            pros=[str(p) for p in raw_output.get("pros", []) if p],
            cons=[str(c) for c in raw_output.get("cons", []) if c],
            key_risks=[str(r) for r in raw_output.get("key_risks", []) if r],
            open_questions=[str(q) for q in raw_output.get("open_questions", []) if q]
        )

        # Merge new proponents/opponents preserving existing unique entries
        new_proponents = list(dict.fromkeys(idea.proponents + [str(p) for p in raw_output.get("proponents", []) if p]))
        new_opponents = list(dict.fromkeys(idea.opponents + [str(o) for o in raw_output.get("opponents", []) if o]))

        print(f"[ProsConsAgent] Completed for '{idea.title}' with {len(enrichment.pros)} pros, {len(enrichment.cons)} cons.")
        return enrichment, new_proponents, new_opponents


pros_cons_agent = ProsConsAgent()

