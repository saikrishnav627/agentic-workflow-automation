import os

os.environ.pop("OPENAI_API_KEY", None)   # use the deterministic planner in tests
