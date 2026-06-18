"""Prompt templates for the AI extraction layer.

We ask the model to return STRICT JSON matching a fixed schema. The pipeline
then validates that JSON with pydantic before anything is stored.
"""
from __future__ import annotations

SYSTEM_PROMPT = (
    "You are a meticulous scientific research extraction assistant. "
    "You read the text of a research paper / study web page and return ONLY a "
    "single JSON object with the requested fields. Do not invent facts: if a "
    "field is not present in the text, use null (or an empty list). Never wrap "
    "the JSON in markdown fences or add commentary."
)

# The exact JSON contract the model must follow.
JSON_SCHEMA_HINT = """\
Return JSON with EXACTLY these keys:
{
  "summary": string | null,        // 2-4 sentence plain-language summary
  "study_type": string | null,     // e.g. "randomized controlled trial",
                                    //      "meta-analysis", "cohort study",
                                    //      "case report", "review", "preprint"
  "sample_size": integer | null,    // number of participants/subjects, if stated
  "key_findings": string[],         // 2-5 concise bullet findings (no markdown)
  "abstract": string | null         // the paper's abstract if present in text
}"""


def build_user_prompt(
    title: str | None,
    existing_abstract: str | None,
    keywords: list[str],
    body_text: str,
) -> str:
    kw = ", ".join(keywords) if keywords else "(none specified)"
    abstract_part = (
        f"\nKnown abstract (may be partial):\n{existing_abstract}\n"
        if existing_abstract
        else ""
    )
    return (
        f"Topic keywords of interest: {kw}\n"
        f"Page title: {title or '(unknown)'}\n"
        f"{abstract_part}\n"
        f"{JSON_SCHEMA_HINT}\n\n"
        "Here is the page text to extract from:\n"
        "-----------------------------------\n"
        f"{body_text}\n"
        "-----------------------------------\n"
        "Respond with the JSON object only."
    )
