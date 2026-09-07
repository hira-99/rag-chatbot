"""One-time bootstrap: seeds the retrieval stores with the fictional
ByteMage corpus used throughout the notebooks, so D is testable before
Section C's real upload pipeline exists. Chunking here is deliberately
simple (paragraph split) -- Section C's ingestion pipeline is the real
chunker; this only needs to produce a few retrievable chunks.

Run directly: python -m app.retrieval.seed_corpus
"""
from app.retrieval import lexical_search, vector_store

DOCUMENTS = {
    "bytemage-overview": {
        "title": "ByteMage Company Overview",
        "text": (
            "ByteMage is a mid-size software company building developer "
            "productivity tools. Founded in 2018, ByteMage is headquartered "
            "in Austin, Texas, with a fully distributed engineering team.\n\n"
            "ByteMage's flagship product is CodeSprint, a project management "
            "tool for software teams. The company also offers ByteMage "
            "Insights, an analytics add-on launched in 2023.\n\n"
            "ByteMage has approximately 220 employees across Engineering, "
            "Sales, Customer Success, and Operations."
        ),
    },
    "bytemage-leave-policy": {
        "title": "ByteMage Leave Policy",
        "text": (
            "Full-time ByteMage employees accrue 20 days of paid time off "
            "(PTO) per year, accrued monthly. Unused PTO up to 5 days may be "
            "carried over into the next calendar year; anything beyond that "
            "is forfeited.\n\n"
            "ByteMage also offers 10 paid sick days per year, which do not "
            "carry over. Parental leave is 16 weeks paid for the primary "
            "caregiver and 6 weeks paid for a secondary caregiver.\n\n"
            "PTO requests must be submitted through the HR portal at least "
            "5 business days in advance for requests longer than 3 days."
        ),
    },
    "bytemage-compensation-policy": {
        "title": "ByteMage Compensation Policy",
        "text": (
            "ByteMage reviews compensation annually every March. Salary "
            "bands are determined by role, level, and location tier.\n\n"
            "Employees are eligible for an annual performance bonus of up "
            "to 15% of base salary, paid out in April following the review "
            "cycle. Equity grants (RSUs) vest over 4 years with a 1-year "
            "cliff.\n\n"
            "Referral bonuses are $2,000 for a successful engineering hire "
            "and $1,000 for other roles, paid after the referred employee "
            "completes 90 days."
        ),
    },
    "bytemage-data-retention-policy": {
        "title": "ByteMage Data Retention Policy",
        "text": (
            "Customer data stored in CodeSprint is retained for the "
            "duration of an active subscription plus 30 days after "
            "cancellation, after which it is permanently deleted.\n\n"
            "Internal audit logs are retained for 1 year. Employee HR "
            "records are retained for 7 years after termination, per legal "
            "requirement.\n\n"
            "Customers may request early deletion of their data at any "
            "time by contacting support; such requests are processed "
            "within 10 business days."
        ),
    },
    "bytemage-engineering-handbook": {
        "title": "ByteMage Engineering Handbook",
        "text": (
            "All code changes at ByteMage require at least one peer review "
            "approval before merging to main. Engineers are expected to "
            "write tests for new functionality.\n\n"
            "ByteMage's on-call rotation is weekly, covering CodeSprint and "
            "ByteMage Insights. On-call engineers must acknowledge pages "
            "within 15 minutes.\n\n"
            "Production deploys happen via CI/CD on merge to main, gated by "
            "automated tests and a manual approval step for the payments "
            "service."
        ),
    },
    "bytemage-product-roadmap": {
        "title": "ByteMage Product Roadmap",
        "text": (
            "In Q3, ByteMage plans to ship a redesigned CodeSprint "
            "dashboard and native GitHub Actions integration.\n\n"
            "Q4 priorities include expanding ByteMage Insights with team "
            "velocity forecasting, and a public API for third-party "
            "integrations.\n\n"
            "Longer-term, ByteMage is exploring an AI-assisted sprint "
            "planning feature, currently in early research."
        ),
    },
    "bytemage-onboarding-guide": {
        "title": "ByteMage Onboarding Guide",
        "text": (
            "New ByteMage employees complete a 2-week onboarding program "
            "covering company tools, security training, and a shadow "
            "period with their team.\n\n"
            "IT provisions a laptop and accounts before day one. New hires "
            "must complete security awareness training within their first "
            "week.\n\n"
            "Each new employee is assigned an onboarding buddy from their "
            "team for the first 30 days."
        ),
    },
}


def _chunks_for(document_id, document):
    paragraphs = [p.strip() for p in document["text"].split("\n\n") if p.strip()]
    return [
        {"chunk_id": f"{document_id}-{i}", "text": paragraph, "title": document["title"], "document_id": document_id}
        for i, paragraph in enumerate(paragraphs)
    ]


def seed():
    total = 0
    for document_id, document in DOCUMENTS.items():
        for chunk in _chunks_for(document_id, document):
            metadata = {"title": chunk["title"], "document_id": chunk["document_id"]}
            vector_store.add_chunk(chunk["chunk_id"], chunk["text"], metadata)
            lexical_search.index_chunk(chunk["chunk_id"], chunk["text"], metadata)
            total += 1
    return total


if __name__ == "__main__":
    count = seed()
    print(f"Seeded {count} chunks from {len(DOCUMENTS)} documents.")
