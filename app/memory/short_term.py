"""Sliding message window (Step 13.4): keep only the most recent turns
verbatim in the prompt; everything older gets folded into the running
summary (summarizer.py) instead of sent in full every time.
"""

RECENT_TURNS_KEPT = 6  # user+assistant pairs kept verbatim


def split_recent_and_archived(messages):
    """messages: a flat list of {"role", "content"} dicts (user/assistant
    only, no system message). Returns (recent, archived) -- archived is
    everything before the last RECENT_TURNS_KEPT user turns.
    """
    user_indices = [i for i, m in enumerate(messages) if m["role"] == "user"]
    if len(user_indices) <= RECENT_TURNS_KEPT:
        return messages, []

    cutoff = user_indices[-RECENT_TURNS_KEPT]
    return messages[cutoff:], messages[:cutoff]
