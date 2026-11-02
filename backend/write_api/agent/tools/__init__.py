"""Tool registry exposed to the LLM: name -> JSON schema -> handler, with Pydantic argument validation."""

from write_api.agent.tools.compute.planning import TOOLS as COMPUTE
from write_api.agent.tools.read.facts import TOOLS as READ
from write_api.agent.tools.terminal.finish import TOOLS as TERMINAL

ALL_TOOLS = READ + COMPUTE + TERMINAL
BY_NAME = {t.name: t for t in ALL_TOOLS}
