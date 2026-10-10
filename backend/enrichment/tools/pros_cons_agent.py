from typing import Optional, Tuple, List
from ..models import Idea, ProConItem, ProsConsEnrichment
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
1. Extract every material PRO and CON actually voiced in the transcript.
2. Categorize each as Technical, Business & Market, User Experience,
   Operations, Compliance & Security, or Financial.
3. Rate each point High, Medium, or Low and sort highest impact/risk first.
4. Include a short speaker-attributed source quote or close paraphrase.
5. Identify assumptions and open questions that still require validation.
6. Extract or refine proponents and opponents.

Return your response in pure JSON format matching this schema:
{{
  "summary": "Overall synthesis of the debate and any conditional consensus",
  "pros": [{{
    "point": "Specific benefit",
    "category": "Operations",
    "severity_or_impact": "High",
    "source_context": "Sarah said ..."
  }}],
  "cons": [{{
    "point": "Specific objection or risk",
    "category": "Compliance & Security",
    "severity_or_impact": "High",
    "source_context": "Elena warned ..."
  }}],
  "key_risks": ["Risk 1...", "Risk 2..."],
  "assumptions": ["Assumption that needs validation"],
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

        def parse_items(items):
            parsed = []
            for item in items if isinstance(items, list) else []:
                if isinstance(item, str):
                    parsed.append(ProConItem(point=item))
                elif isinstance(item, dict) and item.get("point"):
                    severity = str(
                        item.get("severity_or_impact")
                        or item.get("severityOrImpact")
                        or "Medium"
                    ).title()
                    if severity not in {"High", "Medium", "Low"}:
                        severity = "Medium"
                    parsed.append(ProConItem(
                        point=str(item["point"]),
                        category=str(item.get("category") or "General"),
                        severity_or_impact=severity,
                        source_context=str(
                            item.get("source_context")
                            or item.get("sourceContext")
                            or ""
                        ),
                    ))
            priority = {"High": 3, "Medium": 2, "Low": 1}
            return sorted(
                parsed,
                key=lambda value: priority.get(value.severity_or_impact, 0),
                reverse=True,
            )

        enrichment = ProsConsEnrichment(
            summary=str(raw_output.get("summary") or "").strip() or None,
            pros=parse_items(raw_output.get("pros", [])),
            cons=parse_items(raw_output.get("cons", [])),
            key_risks=[str(r) for r in raw_output.get("key_risks", []) if r],
            assumptions=[str(a) for a in raw_output.get("assumptions", []) if a],
            open_questions=[str(q) for q in raw_output.get("open_questions", []) if q]
        )

        # Merge new proponents/opponents preserving existing unique entries
        new_proponents = list(dict.fromkeys(idea.proponents + [str(p) for p in raw_output.get("proponents", []) if p]))
        new_opponents = list(dict.fromkeys(idea.opponents + [str(o) for o in raw_output.get("opponents", []) if o]))

        print(f"[ProsConsAgent] Completed for '{idea.title}' with {len(enrichment.pros)} pros, {len(enrichment.cons)} cons.")
        return enrichment, new_proponents, new_opponents


pros_cons_agent = ProsConsAgent()
