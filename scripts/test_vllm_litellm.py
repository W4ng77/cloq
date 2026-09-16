"""Smoke test: litellm -> vLLM tool call with return_token_ids; compare prompt ids to local rendering."""
import json, sys, time, urllib.request
sys.path.insert(0, "/home/xinyu/cloq")
from cloq.config import AGENT_API_BASE, agent_llm_args
from cloq.context_policy import render_prompt_ids, render_prompt

def wait(url, secs=420):
    t0 = time.time()
    while time.time() - t0 < secs:
        try:
            urllib.request.urlopen(url + "/models", timeout=5); return True
        except Exception:
            time.sleep(5)
    return False

assert wait(AGENT_API_BASE), "server not up"
import litellm
from tau2.registry import registry
from tau2.utils.llm_utils import generate, to_litellm_messages
from tau2.data_model.message import SystemMessage, UserMessage, AssistantMessage
env = registry.get_env_constructor("airline")()
tools = env.get_tools()
tools_schema = [t.openai_schema for t in tools]
print("n tools", len(tools), "tool schema tokens ~", len(json.dumps(tools_schema)))
msgs = [SystemMessage(role="system", content="You are a customer service agent. Use tools."),
        AssistantMessage(role="assistant", content="Hi! How can I help you today?"),
        UserMessage(role="user", content="Hi, my user id is mia_li_3668, can you look up my profile?")]
args = agent_llm_args()
t0 = time.time()
resp = generate(model="hosted_vllm/agent", messages=msgs, tools=tools, call_name="test", **args)
print("gen time", round(time.time()-t0,2), "s")
print("content:", repr(resp.content)[:300]); print("tool_calls:", resp.tool_calls)
raw = resp.raw_data
print("raw keys:", list(raw.keys()))
ptid = raw.get("prompt_token_ids")
print("prompt_token_ids present:", ptid is not None, "len", None if ptid is None else len(ptid))
print("choice keys:", list(raw["choices"][0].keys()))
print("usage:", raw.get("usage"))
lm = to_litellm_messages(msgs)
local_ids = render_prompt_ids(lm, tools_schema)
print("local render len", len(local_ids), "match:", ptid == local_ids if ptid is not None else "n/a")
if ptid is not None and ptid != local_ids:
    from cloq.context_policy import get_tokenizer
    tok = get_tokenizer()
    for i,(a,b) in enumerate(zip(ptid, local_ids)):
        if a!=b:
            print("first diff at", i, repr(tok.decode(ptid[max(0,i-20):i+20])), "||", repr(tok.decode(local_ids[max(0,i-20):i+20]))); break
# second turn with a tool result to check assistant tool-call rendering
if resp.tool_calls:
    from tau2.data_model.message import ToolMessage
    tc = resp.tool_calls[0]
    tr = env.get_response(tc) if hasattr(env, "get_response") else None
    print("tool response type:", type(tr))
    msgs2 = msgs + [resp, ToolMessage(id=tc.id, role="tool", content=str(tr.content if tr is not None else "ok"))]
    resp2 = generate(model="hosted_vllm/agent", messages=msgs2, tools=tools, call_name="test", **args)
    ptid2 = resp2.raw_data.get("prompt_token_ids")
    local2 = render_prompt_ids(to_litellm_messages(msgs2), tools_schema)
    print("turn2 match:", ptid2 == local2, len(ptid2 or []), len(local2))
    if ptid2 is not None and ptid2 != local2:
        from cloq.context_policy import get_tokenizer
        tok = get_tokenizer()
        for i,(a,b) in enumerate(zip(ptid2, local2)):
            if a!=b:
                print("first diff at", i, repr(tok.decode(ptid2[max(0,i-30):i+30])), "||", repr(tok.decode(local2[max(0,i-30):i+30]))); break
    print("resp2 content:", repr(resp2.content)[:300], resp2.tool_calls)
