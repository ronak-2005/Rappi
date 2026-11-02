"""Check an LLM env file before using it:  python -m evals.llm_check llm-examples/x.env [--models]

- prints the endpoint and model (never the key)
- sends a tiny tool-call test: does this endpoint + model actually call tools?
- with --models: lists the model ids the endpoint offers
"""

import sys

from openai import OpenAI

from shared.config.llm_settings import load_llm_settings
from write_api.services.run_service import llm_health


def main(argv: list[str]) -> int:
    env = argv[0] if argv and not argv[0].startswith("--") else "llm.env"
    s = load_llm_settings(env)
    print(f"env: {env}\nbase_url: {s.llm_base_url}\nmodel: {s.llm_model or '(not set)'}\n"
          f"api key set: {bool(s.llm_api_key)}")
    if "--models" in argv:
        client = OpenAI(base_url=s.llm_base_url, api_key=s.llm_api_key or "none", timeout=30)
        for m in sorted(client.models.list(), key=lambda m: m.id):
            print("  ", m.id)
        return 0
    h = llm_health(s)
    print(f"ok: {h['ok']}  tools_supported: {h.get('tools_supported')}")
    if not h["ok"]:
        print("error:", h.get("error"))
    elif h.get("reply"):
        print("reply:", h["reply"])
    return 0 if h["ok"] and h.get("tools_supported") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
