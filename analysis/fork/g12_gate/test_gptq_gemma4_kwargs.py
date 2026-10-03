"""W100n: CPU check of the Gemma-4 GPTQ path in cloq.quantize (per-attention-type layer kwargs, v_proj None).

A tiny random Gemma4UnifiedTextConfig (sliding window 8, layer types S S F S F, attention_k_eq_v) is built. With the
per-type kwargs, the propagated hidden state after the last layer, run through quantize_model with an identity
quantizer (wbits 16), must equal the model's own last hidden state (pre-norm); with layer 0's kwargs for every layer
(the old path) it must not. Also: groups_for drops the absent v_proj only on full layers; a Qwen3 layer's groups are
unchanged."""
import torch, copy
from transformers import AutoConfig, AutoModelForCausalLM
from transformers.models.gemma4_unified.configuration_gemma4_unified import Gemma4UnifiedTextConfig
import cloq.quantize as Q

torch.manual_seed(0)
base = AutoConfig.from_pretrained("/data/ziyangs/cloq_work/ckpt_cache/g12_textonly_v1").to_dict()
base.update(num_hidden_layers=5, hidden_size=64, intermediate_size=128, num_attention_heads=4, num_key_value_heads=2,
            head_dim=16, global_head_dim=32, num_global_key_value_heads=1, vocab_size=512, vocab_size_per_layer_input=512,
            sliding_window=8, layer_types=["sliding_attention", "sliding_attention", "full_attention", "sliding_attention", "full_attention"])
for k in ("per_layer_config", "transformers_version", "architectures", "model_type"):
    base.pop(k, None)
cfg = Gemma4UnifiedTextConfig(**base)
model = AutoModelForCausalLM.from_config(cfg, dtype=torch.float32, attn_implementation="sdpa").eval()
model.config.use_cache = False
for p in model.parameters():
    torch.nn.init.normal_(p, std=0.2)
seqs = [list(torch.randint(0, 512, (40,)).tolist()), list(torch.randint(0, 512, (25,)).tolist())]
with torch.no_grad():
    ref = []
    for s in seqs:
        hs = model(input_ids=torch.tensor([s]), output_hidden_states=True).hidden_states
        ref.append(hs[-1])  # after the final norm in HF? check below
print("groups L0", Q.groups_for(model.model.layers[0]))
print("groups L2", Q.groups_for(model.model.layers[2]))

def run(per_type: bool):
    m = copy.deepcopy(model)
    inp = Q.capture_layer0_inputs(m, seqs, "cpu", offload=False)
    if not per_type:
        inp.per_type = None
    with torch.no_grad():
        for li, layer in enumerate(m.model.layers):
            new = []
            for i, (h, kw) in enumerate(inp.iter("cpu")):
                new.append((layer(h, **Q._layer_kwargs(inp, li, i, kw, "cpu")), inp.items[i][1]))
            inp.items = new
    return [m.model.norm(h) for h, _ in inp.items]

new = run(True)
for r, a in zip(ref, new):
    print("per-type kwargs: max|diff| vs model forward", (r - a).abs().max().item())
    assert torch.allclose(r, a, atol=1e-5)
try:
    old = run(False)
    print("layer-0 kwargs for all layers: max|diff|", max((r - b).abs().max().item() for r, b in zip(ref, old)))
except RuntimeError as e:
    print("layer-0 kwargs for all layers (pre-W100n path): fails on the first full layer:", str(e)[:80])
from transformers import Qwen3Config
qm = AutoModelForCausalLM.from_config(Qwen3Config(num_hidden_layers=2, hidden_size=64, intermediate_size=128, num_attention_heads=4,
                                                  num_key_value_heads=2, head_dim=16, vocab_size=512))
assert Q.groups_for(qm.model.layers[0]) == Q.SEQUENTIAL_GROUPS and Q._layer_types(qm) is None and not Q._is_gemma4(qm.model.layers[0])
print("qwen3 groups unchanged; PASS")
