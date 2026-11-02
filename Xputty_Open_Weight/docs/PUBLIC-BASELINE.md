# Reproducible public conversation comparison

Two explicitly separate artifacts:

* **48,116,224 parameters, scratch:** the 8K-token Xputty model learns from random
  weights, using mixed 256/512/1024/2048-token windows. This is the capacity experiment.
* **134,515,008 parameters, pretrained comparison:** SmolLM2-135M-Instruct, with only
  the last four blocks and final norm adapted on assistant responses. Its language
  competence is inherited from extensive upstream pretraining. It is never substituted
  for the 48M model and is not a matched-compute architecture ablation.

The dataset is [HuggingFaceTB/smol-smoltalk](https://huggingface.co/datasets/HuggingFaceTB/smol-smoltalk),
revision `f73fe857d519ff6ac5af2ea67c4d3834da7b8bcc`. The upstream dataset declares
Apache-2.0 and synthetic origins. Pinned Parquet originals and checksums are kept
separately from selected working text. Only short conversational components are
selected; fenced code and malformed/nonalternating records are excluded. Source
roles remain known; speech timestamps are absent and are never invented.

The model source is [SmolLM2-135M-Instruct](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct),
revision `12fd25f77366fa6b3b4b768ec3050bf629380bac`, declared Apache-2.0 upstream.
Original model/data cards, license text, hashes and revision identifiers accompany
the local control export. Code remains under the repository's own software license.

## Run it

Use Python 3.11 and the application's existing environment. Install the optional
collector dependency once:

```
python -m pip install -r requirements-public.txt
python tools/public_baseline.py prepare --project storage/NEW_PROJECT_ID --cache storage/public-source-cache
python tools/public_baseline.py scratch --project storage/NEW_PROJECT_ID --steps 200
python tools/public_baseline.py control --project storage/NEW_PROJECT_ID --cache storage/public-source-cache --output storage/NEW_CONTROL_ID --steps 40
```

Use a fresh project/control directory. A browser-visible project ID must contain
32 hexadecimal characters. Preparation freezes a public-data snapshot with 2,000
conversations: 1,400 train, 300 validation, 300 test. The tokenizer sees only train.
The independent official upstream test subset is preserved separately. Do not change
files in a prepared experiment; create a new snapshot for a different collection.
The 48M run can continue with a higher total `--steps` value or through the canvas.

The control uses the first 1,000 eligible training conversations, and a fixed 24
validation/24 final-test subset, training only assistant targets. Validation selects
the best checkpoint, including update zero if adaptation worsens it. Final test is
run after selection. Its adapter checkpoint is for audit; the current control CLI
starts a fresh adaptation and does not provide resume. Exact resume remains available
in the 48M scratch pipeline.

**Pretraining contamination matters:** SmolLM2 was already tuned on Smol-SmolTalk.
These partitions are held out of our adaptation, not necessarily of upstream
pretraining. Do not report their control loss as novel generalization. Exact
full-conversation deduplication is not semantic/near-duplicate decontamination.

After export:

```
python tools/public_baseline.py evaluate --project storage/NEW_PROJECT_ID --output storage/NEW_PROJECT_ID/export
python tools/public_baseline.py evaluate --project storage/NEW_PROJECT_ID --output storage/NEW_CONTROL_ID/export
python export_chat.py --model storage/NEW_CONTROL_ID/export --port 8792
```

The last command prints a private localhost browser link. Chat uses the supplied
local export and its actual chat template; no remote inference or fallback model.
Context budget and response length are independently adjustable. An 8K architecture
limit does not imply our short adaptation trained 8K dependencies.

## Compare behavior

`behavioral-evaluation.json` contains fixed original probes, full responses,
latencies, weights hash and simple indicators. Judge relevance, complete thoughts,
contradictions, recall, uncertainty and useful podcast participation by reading the
responses. Keyword presence and repetition diagnostics are not coherence scores.
Raw token losses must not be compared between models with different vocabularies.

For the scratch model compare fixed held-out loss against its own random checkpoint,
plus the same behavioral probes over time. Record processed tokens and actual window
exposure. Hundreds of updates are early learning evidence, not proof of a viable host.

This baseline does not train voices, speech timing, facial animation, audience interaction,
or response-pool scheduling. No private podcast captures, keys, or weights are included
in the application GitHub distribution. Model exports remain separate local artifacts.
