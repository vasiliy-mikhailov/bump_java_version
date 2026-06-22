#!/usr/bin/env python3
"""In-container OpenHands headless runner for the unified 3-agent harness. Runs the OpenHands
SDK agent with LocalWorkspace on <workdir>, driven by the SAME prompt opencode/kilo get (skill
via /skill mount + AGENTS.md), NO skill-loader, NO harness force-apply. Env: OC_BASE, OC_MODEL,
OC_KEY. Args: <workdir> <prompt>."""
import os, sys, traceback
workdir, prompt = sys.argv[1], sys.argv[2]
try:
    from openhands.sdk import LLM, Agent, Conversation, LocalWorkspace
    from openhands.tools.preset.default import get_default_tools
    from openhands.sdk.context.condenser import LLMSummarizingCondenser
    from pydantic import SecretStr
    # RLVR / AGENTS.md P15 (no pre-defense, no pre-limit): the HARD per-command timeout -> ~1 year (the model
    # used to pick ~120s, which killed cold `bapply` mid-download). The no-change stall detector is ALSO set to
    # a year: the original 300s cap pre-armed against a hypothetical, and its real trigger (a git pager / a test
    # blocked on stdin) was ROOT-FIXED at source (P16) — GIT_PAGER=cat + stdin</dev/null in the bin/ verbs — so
    # the cap is now a guard we have not earned. A genuinely new stall is met and root-caused when it occurs.
    ONE_YEAR = 31536000
    NO_CHANGE = ONE_YEAR
    import openhands.tools.terminal.constants as _c
    import openhands.tools.terminal.terminal.terminal_session as _ts
    import openhands.tools.terminal.terminal.interface as _if
    _c.NO_CHANGE_TIMEOUT_SECONDS = _ts.NO_CHANGE_TIMEOUT_SECONDS = _if.NO_CHANGE_TIMEOUT_SECONDS = NO_CHANGE
    from openhands.tools.terminal.impl import TerminalExecutor as _TE
    _orig_call = _TE.__call__
    def _no_timeout_call(self, action, *a, **k):
        try: object.__setattr__(action, "timeout", ONE_YEAR)   # hard timeout only -> never cut a progressing build
        except Exception:
            try: action.timeout = ONE_YEAR
            except Exception: pass
        return _orig_call(self, action, *a, **k)
    _TE.__call__ = _no_timeout_call
    print("PATCHED: hard timeout -> 1 year; no-change stall detector -> 1 year (root cause fixed at source, P15)")
    base, model, key = os.environ["OC_BASE"], "openai/" + os.environ["OC_MODEL"], SecretStr(os.environ["OC_KEY"])
    llm = LLM(model=model, base_url=base, api_key=key, usage_id="ohrun",
              max_output_tokens=32768, temperature=0.0, native_tool_calling=True)
    cond = LLM(model=model, base_url=base, api_key=key, usage_id="ohcond",
               max_output_tokens=32768, temperature=0.0, native_tool_calling=False)
    agent = Agent(llm=llm, tools=get_default_tools(enable_browser=False),
                  condenser=LLMSummarizingCondenser(llm=cond, max_size=40, keep_first=2))
    # NO step/iteration cap (RLVR: a budget/limit teaches the model to give up and emit noise — AGENTS.md P15).
    conv = Conversation(agent=agent, workspace=LocalWorkspace(working_dir=workdir), max_iteration_per_run=sys.maxsize)
    conv.send_message(prompt)
    conv.run()
    print("OH_RUN_DONE")
except Exception as e:
    traceback.print_exc()
    print("OH_RUN_ERROR", e)
