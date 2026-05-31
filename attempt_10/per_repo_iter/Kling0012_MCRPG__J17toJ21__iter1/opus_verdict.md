# Claude+Opus verdict — Kling0012_MCRPG (J17->J21)  [FIXED + VALIDATED]
VERDICT: FIXABLE (confirmed at all 3 rungs with the imperative-prompt fix)
- Original OH+Qwen failure: agent wandered (mvn test x7, probed docker wrapper, inv=0) -> never ran bump.
- Fix (artifact change, generalizes): "Execution discipline" preamble at top of prompt.md — forbid toolchain
  investigation (which docker / mvn wrapper / /opt scripts), run each flow step once, REACH the bump (Step 3) early.
- Ladder re-validation with the fix:
  * Opus rung (deterministic): PASS (pom=21).
  * Claude+Qwen rung: PASS in 84.6s/18 turns — reached bump immediately, compiled+tested under 21.
  * Claude+OpenHands+Qwen rung: PASS — ran bump (inv=3 vs orig 0), bump complete, compile+test pass, finished.
- Dialogues: dialogue.qwen.log (Kling0012_MCRPG__imptest), /tmp/kling_ohtest.log.
