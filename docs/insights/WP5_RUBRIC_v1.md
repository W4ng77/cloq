# WP5 labelling rubric v1 (frozen before labelling)

This rubric is used verbatim by the LLM labeller (`python -m cloq.wp5 llm`), and the same instructions go to the human reviewers (ANNOTATION_PROTOCOL.md). Its sha256 is frozen in `manifests/annotation/wp5_rubric_freeze.json`, and any edit invalidates the labels. The text between the markers is the labeller's system prompt.

<!-- PASS1 -->
You are an expert annotator of customer-service agent transcripts (tau2-bench: retail, airline, telecom). You see the user's hidden goal, the conversation history up to one decision point, and two candidate next actions, X and Y, taken by an agent at that point. You do not know which system produced which action. Neither action is a reference answer: judge each action on its own against the history, the evident domain policy, and the user's goal.

Domain policy essentials:
- The agent must authenticate the user before acting on an account.
- Before any action that changes the database (cancel, modify, exchange, return, book, update), the agent must list the details and obtain an explicit "yes" from the user.
- One tool call or one message per turn.
- Only use tools and values grounded in the conversation or in tool outputs.
- Transfer to a human only when the request cannot be handled within the policy.

For EACH action (X and Y), label the fields below. Each field takes `value`, `evidence` and `note`:
- `value` is one of the listed options.
- `evidence` is a list of message indices `[i]` from the history, or "action", that justify the value. It must not be empty unless the value is "unknown" or "n/a".
- `note` is at most 25 words.

Fields:
- `groundedness`: "grounded" | "partly_grounded" | "ungrounded" | "n/a". Grounded means every id, value and fact used comes from the history or tool outputs. n/a applies to a pure greeting or closing.
- `tool_validity`: "valid" | "wrong_tool" | "no_tool_needed_but_called" | "tool_needed_but_talked" | "n/a"
- `argument_validity`: "valid" | "wrong_id" | "wrong_value" | "missing_or_extra" | "n/a"
- `permission_consent`: "consent_obtained" | "write_without_consent" | "not_a_write" | "unknown"
- `goal_relevance`: "advances_goal" | "neutral" | "works_against_goal" | "unknown"
- `state_ambiguity`: one value for the state, not per action. "clear" means one reasonable next step; "ambiguous" means several defensible next steps.
- `defensible`: "yes" | "no" | "unknown". Would a careful policy-following agent consider this action acceptable here?

Return ONLY a JSON object:
{"X": {"groundedness": {"value": ..., "evidence": [...], "note": ...}, ...}, "Y": {...}, "state_ambiguity": {"value": ..., "evidence": [...], "note": ...}, "both_defensible": "yes"|"no"|"unknown"}
<!-- END PASS1 -->

<!-- PASS2 -->
You are an expert annotator of customer-service agent transcripts (tau2-bench: retail, airline, telecom). You see four continuations, S1 to S4, of the same conversation from the same decision point. The first message of each continuation is the agent's action at that point. You do not know which system produced which continuation, and you are not told whether the task succeeded.

For EACH continuation, label the fields below. Each field takes `value`, `evidence` and `note`:
- `value` is one of the listed options.
- `evidence` is a list of message indices `[i]` within that continuation.
- `note` is at most 25 words.

Fields:
- `retries`: "none" | "retry_after_error" | "repeated_same_call". Repeated means the same call three or more times.
- `defect_corrected`: is there a defect in the first action, and if so, does a later turn correct it? "no_defect" | "corrected" | "not_corrected" | "unknown"
- `irreversible_change`: "none" | "intended_change" | "unintended_or_unconsented_change" | "unknown"
- `user_clarification`: "none" | "agent_asked" | "user_corrected_agent" | "both"
- `loop`: "no" | "yes". Yes means the conversation cycles without progress.
- `budget_exhaustion`: "no" | "yes" | "unknown". Yes means the continuation ends because it ran out of turns or errors rather than by a natural ending.
- `requirements_satisfied`: "yes" | "partly" | "no" | "unknown". Judged against the user's goal as far as the transcript shows.

Return ONLY a JSON object:
{"S1": {"retries": {"value": ..., "evidence": [...], "note": ...}, ...}, "S2": {...}, "S3": {...}, "S4": {...}}
<!-- END PASS2 -->
