"""OpenAgent-X reference kernel.

A stdlib-only, model-agnostic agent core that is the runnable reference
implementation of the OpenAgent-X universal contracts (``schemas/``) and the
engineering blueprint (``docs/blueprint/``).

Design pillars (each maps to one module):

======================  ==================================================
Pillar                  Module
======================  ==================================================
X-Trace                 :mod:`openagentx.events`, :mod:`openagentx.trace`
X-Gateway (routing)     :mod:`openagentx.llm`
X-Budget                :mod:`openagentx.budget`
X-Loop                  :mod:`openagentx.loop`
X-Guard                 :mod:`openagentx.policy`
X-Tools                 :mod:`openagentx.tools`, :mod:`openagentx.builtins`
X-Memory                :mod:`openagentx.memory`
X-Prompt                :mod:`openagentx.prompts`
X-Packs                 :mod:`openagentx.packs`
X-Team                  :mod:`openagentx.team`
======================  ==================================================

Core rules enforced across the kernel:

1. **Files over databases** — every artifact is human-readable and diffable.
2. **Zero required dependencies** — the core imports nothing outside stdlib.
3. **One authority per concern** — policy decisions live in the policy engine,
   never in prompts or handler code.
4. **Budget before action** — no loop iteration starts without budget headroom.
5. **Events before effects** — every state transition is persisted as an
   ``EventEnvelope`` *before* the side effect it describes is attempted.
"""

from openagentx.events import Actor, EventEnvelope, EventType
from openagentx.trace import TraceLog
from openagentx.llm import EchoLLM, LLMResponse, OpenAICompatLLM, RouterLLM, Usage

__version__ = "0.1.0"

__all__ = [
    "Actor",
    "EchoLLM",
    "EventEnvelope",
    "EventType",
    "LLMResponse",
    "OpenAICompatLLM",
    "RouterLLM",
    "TraceLog",
    "Usage",
    "__version__",
]
