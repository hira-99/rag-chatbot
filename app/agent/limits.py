"""Step limit shared by the agent loop -- a hard ceiling on tool-calling
rounds within a single turn, so a confused model can't loop forever."""

MAX_STEPS = 6
