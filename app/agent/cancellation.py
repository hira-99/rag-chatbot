"""Cancellation for agent runs.

No separate flag or polling loop -- run_agent (loop.py) is a generator that
yields between every model/tool call, and app/main.py wires it into
Gradio's native cancels= (proven in A.6 for plain streaming). Clicking Stop
raises GeneratorExit at the loop's current yield point: whatever tool call
is in flight finishes (it's a plain function call, not interruptible
mid-execution), but no further model or tool call starts, and nothing
half-finished gets persisted -- the same guarantee A.6 established for
streaming.
"""
