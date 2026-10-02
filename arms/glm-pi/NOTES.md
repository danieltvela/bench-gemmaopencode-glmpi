# Arm B: GLM-5.3-Flash + pi (plain control)

This arm is defined by its emptiness: the stronger model on the minimal
harness, with pi's default system prompt and no project instructions.

- Do NOT add AGENTS.md, CLAUDE.md, skills, prompt templates, or pi config
  here, and do not seed any of those into its workspace. Even if something
  leaks in, the canonical invocation enforces isolation:

  ```bash
  pi -p --no-session --no-context-files --no-skills \
    --model "$BENCH_GLM_MODEL_ID" "$(cat prompt.md)"
  ```

- The provider/model comes from the global `~/.pi/agent/models.json`. Set
  `BENCH_GLM_MODEL_ID` to the `provider/model` id that configuration exposes;
  the endpoint is configured through `BENCH_GLM_BASE_URL` (see README).
- Global pi extensions are part of the installed harness; leave them alone
  rather than "leveling the field" mid-experiment.
