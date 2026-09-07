"""Source numbering and citation validation."""
import re

CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def assign_source_numbers(chunks):
    """Number retrieved chunks [1..n] in the order they're shown to the
    model, so its [n] citations can be checked against real chunk ids."""
    sources = []
    for i, chunk in enumerate(chunks, start=1):
        sources.append({
            "number": i,
            "chunk_id": chunk["chunk_id"],
            "title": chunk.get("metadata", {}).get("title", ""),
            "text": chunk["text"],
        })
    return sources


def format_sources_for_prompt(sources):
    return "\n\n".join(f"[{s['number']}] {s['title']}\n{s['text']}" for s in sources)


def validate_citations(answer_text, sources):
    """Every [n] the model wrote must refer to a source it was actually
    given -- catches both fabricated numbers and off-by-one errors."""
    cited = {int(n) for n in CITATION_PATTERN.findall(answer_text)}
    valid = {s["number"] for s in sources}
    unknown = sorted(cited - valid)
    return {
        "cited_numbers": sorted(cited),
        "unknown_citations": unknown,
        "is_valid": not unknown,
    }
