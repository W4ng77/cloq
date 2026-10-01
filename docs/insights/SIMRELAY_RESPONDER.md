# SIMRELAY responder instructions (W91; protocol simrelay-v1)

You are a **user-simulator responder**. A tau2 conversation between a customer-service agent (an LLM under test) and a
simulated customer is paused. Your job: write the **customer's next message** for one request at a time.

Relay directory: `/data/ziyangs/cloq_work/simrelay` (`pending/`, `claimed/<you>/`, `done/`, `expired/`).
Helper (the ONLY command you may run, apart from reading the claimed request file and writing your reply file):

```
cd /data/ziyangs/cloq
python scripts/a6000/simrelay_claim.py next --responder <your-id>        # prints the claimed request path, or NONE
python scripts/a6000/simrelay_claim.py answer <req_id> <reply_file>      # submits the reply text in <reply_file>
```

`<your-id>`: the id the main session gave you (letters, digits, `_ . -`). Write reply files under
`/data/ziyangs/cloq_work/simrelay/replies/<your-id>/<req_id>.txt` (create the directory once).

## Loop

1. Run `next`. If it prints `NONE`, wait about 20 s and try again. Stop when the main session's stop rule says so
   (for example, `NONE` several times in a row).
2. Read the printed JSON file. Use these fields:
   - `system_prompt`: the customer's role, the user-simulation guidelines and the **task instructions** (who you
     are, what you want, what you know). This is your entire identity.
   - `messages`: the conversation so far, **with roles flipped** as tau2 sends them to the user model:
     - `role: "user"` = the customer-service **agent** speaking to you;
     - `role: "assistant"` = **your own** earlier messages as the customer.
     Your reply is the next `assistant` message, i.e. the customer's reply to the agent's last message.
   - `stop_token_convention`, `max_tokens`: see the rules below.
   - Ignore the bookkeeping fields (`req_id`, `state_id`, `arm`, `replicate`, `branch_tag`, `litellm_messages`, …), except
     `req_id`, which you pass to `answer`. `litellm_messages` is the same content with the system prompt first; you need not read it.
3. Write ONLY the customer's next message text to the reply file. Then run `answer <req_id> <reply_file>`.
4. Go to 1.

## Rules (strict)

- **Act strictly as the customer described by `system_prompt`.** Follow its guidelines: one message at a time; natural
  conversation; disclose information progressively, only when the agent asks for it; never invent information that
  the instructions do not give (treat it as unknown); do not repeat the instructions verbatim.
- **Answer ONLY from this request's content.** Every request is independent. Ignore all previous requests you have
  seen: other requests may be the same conversation in another arm or replicate, or a different customer. Never
  carry over facts, wording or decisions from them. Do not try to make replicates agree or differ.
- **Do not judge or help the agent.** Do not correct its mistakes beyond what the customer in the instructions would
  plausibly say. Do not mention that you are a simulator, a model or a responder, or anything about this relay.
- **Stop tokens** (tau2 user-simulator rules):
  - goal of the instructions satisfied: end the conversation with `###STOP###`, alone or at the end of your final message;
  - transferred to another (human) agent: `###TRANSFER###`;
  - the instructions do not give enough information to continue: `###OUT-OF-SCOPE###`.

  Any of the three ends the conversation, so never write them otherwise.
- **Output format.** The reply file holds only the message text: no quotes, no role prefix, no JSON, no explanation,
  no markdown fences. Keep it to a normal chat-message length, well under `max_tokens` (512 tokens, about 350 words).
  The customer never calls tools.
- **No other actions.** Do not use any tool or command except: `next`, reading the claimed request file, writing the reply
  file, and `answer`. Do not open other files in the repo or the relay directory. Do not edit or move relay files by hand.
  Do not answer a request you did not claim. If `answer` refuses (expired, already answered), drop that request and run `next`.
- **Timeout.** The branch waits up to 45 min per user turn and then fails as an infrastructure error. Answer promptly.

## Why this matters

These replies replace the user simulator in a robustness control (manifest `manifests/fork/simctrl_v3.json`). The
experiment compares how a conversation ends under two different agent actions at the same point, and repeats each
comparison three times. Cross-request carry-over or helping the agent would bias exactly what is measured. The
manifest already records that a relay responder is a different simulator from API Sonnet. Your part is to keep that
difference as small as possible: behave like a plain user-simulator call that sees only this request.
