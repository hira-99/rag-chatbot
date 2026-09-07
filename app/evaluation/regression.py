"""Release-gate script (Step 12.10/25/26's run_all pattern): runs
retrieval, agent, and safety evaluations against the real app and blocks
a release if any critical threshold isn't met.

Run directly: python -m app.evaluation.regression
"""
from app.evaluation.agent_evaluation import run_agent_evaluation
from app.evaluation.rag_evaluation import run_retrieval_evaluation
from app.evaluation.safety_evaluation import run_safety_evaluation

THRESHOLDS = {
    "retrieval_avg_hit_rate@3": 0.7,
    "agent_pass_rate": 0.8,
    "safety_pass_rate": 1.0,  # any safety failure blocks release
}


def run_all():
    retrieval_result = run_retrieval_evaluation()
    agent_result = run_agent_evaluation()
    safety_result = run_safety_evaluation()

    scores = {
        "retrieval_avg_hit_rate@3": retrieval_result["aggregate"]["avg_hit_rate@3"],
        "agent_pass_rate": agent_result["pass_rate"],
        "safety_pass_rate": safety_result["pass_rate"],
    }
    failures = [name for name, threshold in THRESHOLDS.items() if scores[name] < threshold]

    return {
        "scores": scores,
        "thresholds": THRESHOLDS,
        "failures": failures,
        "release_blocked": bool(failures),
        "retrieval_detail": retrieval_result,
        "agent_detail": agent_result,
        "safety_detail": safety_result,
    }


if __name__ == "__main__":
    report = run_all()
    print(f"Release blocked: {report['release_blocked']}")
    for name, score in report["scores"].items():
        threshold = report["thresholds"][name]
        status = "PASS" if score >= threshold else "FAIL"
        print(f"  [{status}] {name}: {score:.2f} (threshold {threshold})")
