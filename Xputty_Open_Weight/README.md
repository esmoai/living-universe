# Xputty Open Weight

**Your material → your model.** A local-first browser canvas for collecting material, reviewing it, training a small language model, auditioning it and exporting portable weights.

## Public conversation baseline

Version 0.5.1 adds a reproducible public-data experiment and a **separate pretrained
135M control**. The 48M model still trains from random weights. Both use pinned,
attributed synthetic conversation material with independent adaptation partitions;
neither invents audio timestamps. The comparison exports its actual model, provenance,
assistant-only training report and fixed behavioral probes. It is never silently
used as the scratch model. See [the full protocol](docs/PUBLIC-BASELINE.md) for commands,
licenses, source revisions and the important upstream-pretraining overlap limitation.

Public collection needs the optional `requirements-public.txt`. It is not installed
or downloaded merely by opening the canvas. Existing projects and private data stay
independent of this experiment.

The standalone application lives in `Xputty_Open_Weight/` on the
`xputty-open-weight-48m` branch. The esmoai distribution is isolated from Living
Universe's browser/OS sources and has no kernel integration. Xputty application
code retains its own AGPL-3.0 license; upstream model/data licenses remain separate.

The [podcast distillation and quantization lab](docs/DISTILLATION-AND-QUANTIZATION.md)
adds versioned teacher responses, an auditable editorial review, assistant-only
student adaptation, native GGUF probes, four original character profiles, and a
resumable CPU quantized-base LoRA experiment. The small controls produced negative
quality results despite improved loss; these are documented rather than presented
as finished hosts. The 1.5B adapter remains a separate pretrained experiment.

## 48M research build (0.5.1)

This branch is `xputty-open-weight-48m`. New projects default to a **48,116,224-parameter**
LLaMA-style decoder: 12 layers, width 512, 8 attention heads, feed-forward width 1,472,
8,192 vocabulary entries and 2,048 maximum context tokens. It trains from random
initialization. The 1.6M quick-test preset remains available; pre-existing projects
without a preset continue using their original architecture and tokenizer.
Create a **new project** for 48M. Changing a checkpoint's label does not expand its weights.

1. Select **48M · mixed-context research** and the material format.
2. Add and review your sources. Timestamped transcripts use podcast mode; books and
   untimed prose can use plain mode. Originals and whole-source holdouts are preserved.
3. Optionally open **Context mix & learning schedule**. The defaults mix
   256/512/1,024/2,048-token windows with weights 4/3/2/1. A 1,000-update ramp unlocks
   lengths in four stages; short windows remain in the mix. Ramp 0 includes every
   length immediately, covering each once before weighted sampling.
4. Set a total update target and build. Small targets verify operation; they do not
   produce a coherent conversational host. The activity view reports live context,
   tokens/second and the last saved update. Settings lock at first build.
5. Continue to a higher total target to resume the optimizer, curriculum and learning
   schedule. This does not restart warmup. The previous completed model ZIP is retained.
6. **Open chat** uses the actual exported weights. Context and response-token budgets
   are independently selectable. Download includes the same portable chat script,
   Safetensors, GGUF, training policy, actual window exposure and evaluation reports.

Activation checkpointing is enabled for 48M. Microbatches accumulate to at least
512 input-token positions per update; a long window can exceed that minimum.
Warmup is 100 updates, followed by cosine decay through a fixed 10,000-update horizon.
The horizon is separate from the requested stop target so extending a run does not
silently change its schedule. Architecture and policy changes require a new project.
Actual source tokens and padding are distinguished in the training report.

The local Windows CPU acceptance run used the full 48M model, all four window lengths,
and exact checkpoint resume. Reported numerical export checks cover each selected
context length. This verifies mechanics, not fluency, factual grounding or long-context
retrieval quality. CPU training is substantially slower than the 1.6M baseline.
GPU/MPS acceleration and GPU memory usage have not been hardware-verified here.

The maximum context is a capacity limit. **See `context_updates` and `metrics.by_context`
for what was actually trained and evaluated.** Running four short updates with a
progressive ramp does not train 2,048-token dependencies. Stops request a safe update
boundary and checkpoint; an unresponsive job is terminated after the grace period,
preserving its last completed save.

The local launcher uses **http://127.0.0.1:8791** so the original build can stay running.
Codespaces continues to forward port 8787. To test this branch, use the repository's
**Code → Codespaces** menu while `xputty-open-weight-48m` is selected. A fresh Codespace
installs Python 3.11 dependencies and starts the authenticated canvas automatically.
Existing Codespaces must pull this branch and restart their worker; a new Codespace
keeps old experiments independently accessible. No paid worker is provisioned by this app.

CLI users can train a prepared 8K-vocabulary corpus with:
`python -m vox.train --data DATA --run RUN --preset research-48m-v1 --steps 1000`.
The browser worker additionally handles ingestion, evaluation, export and packaging.
The 48M preset requires enough varied text to train its 8,192-token vocabulary; it
fails clearly if a tiny fixture cannot supply that vocabulary.

## The 1800s experiment

Press **1800s experiment ↗** to create a separate plain-prose project and collect
16 English works first published in 1800–1899. Downloads use a
[listed Project Gutenberg mirror](https://www.gutenberg.org/MIRRORS.ALL),
at one request every two seconds. No podcast project is modified.
Review or remove books before pressing **Build my model**. The starter selects
2,000 total updates. Raise the total to continue the same model later;
the previous model ZIP is preserved under `exports-history/`.

The pilot combines novels, memoir, essays, science and philosophy. It is
literature-heavy and is not a representative sample of nineteenth-century society.
`historical-sources.json` records work publication dates, known edition differences,
source URLs and original/working SHA256 checksums. Modern ebook release dates are
never mistaken for historical dates. Original downloads retain their license text;
training copies exclude PG headers/footers and identified modern editorial notes.
This targeted audit is not an exhaustive guarantee that every digitized edition is pure.

Training starts from random weights, with no modern pretrained base. It uses raw
prose plus document-end markers, never fabricated podcast timing or dialogue turns.
Whole books are held out for validation and testing, and the tokenizer sees training
books only. For a command-line experiment:

```
python tools/history1800.py --root storage/18011801180118011801180118011801 --steps 2000
```

Use a new root for a new collection. To resume an existing prepared experiment:
`python worker.py storage/18011801180118011801180118011801 --steps 4000`.
The number is a total target, not additional updates. Browser continuation archives
the previous export; direct worker invocation does not automatically archive it.

When complete, press **Open chat ↗**. Chat runs the **exported Safetensors**, without
a training checkpoint or a fallback model. Each response identifies the weights hash,
generation time and rolling context truncation. Chat framing is experimental:
prose pretraining does not itself teach instruction following. Select **Continue a
passage** to test the model's actual training task directly. Clear starts a fresh
conversation; history lives in that tab and is never silently added to training.

The downloaded model ZIP includes `model/chat.py`. With its documented dependencies
installed, run `python chat.py` from the model directory and open the complete local
link printed in the terminal. This works without Xputty's server or training files.
GGUF and Modelfile are included for `ollama create xputty-1800s -f Modelfile`.
Browser generation uses CPU; GGUF/Ollama acceptance is reported separately.

For larger collections, Project Gutenberg documents
[bulk/mirror access](https://www.gutenberg.org/help/mirroring.html).
The Library of Congress offers [bulk newspaper OCR](https://www.loc.gov/collections/chronicling-america/datasets/)
and [its current newspaper API](https://www.loc.gov/apis/additional-apis/chronicling-america-api/).
Filter newspaper issue dates to 1800–1899 before adding text; OCR requires additional
quality review. The built-in collector intentionally downloads only the dated starter,
not the entire Gutenberg archive. Add other reviewed UTF-8 `.txt` or `.md` works
to a fresh plain-prose project before training. Do not use author birth dates or
digitization dates as evidence that the text itself was written in the 1800s.

Version **0.5.1**. Windows CPU acceptance is tested locally; GitHub Actions runs the same suite on Windows, Linux and macOS and builds per-OS packages. Successful branch builds attach packages to the namespaced `xow-v0.5.1` GitHub release. An OS package includes source, launchers, the English Vosk model and Apache Tika. Python packages are installed on first launch: these are not standalone native executables or fully offline installers.

## Open the canvas

Install **64-bit Python 3.11** and extract a distribution ZIP.

| System | Start |
|---|---|
| Windows x64 | Double-click `START-WINDOWS.cmd` |
| macOS Apple Silicon | Open `START-MAC.command` (or `sh start.sh` in Terminal) |
| Linux x64 | Run `sh start.sh` |

First start creates an isolated `.venv` and installs requirements. Chrome opens at **http://127.0.0.1:8791** with the worker access key. Another installed browser is used if Chrome is absent. Keep the worker running while building; closing a browser tab does not stop a build. `python launch.py --no-browser` starts without opening a window. The old VOX studio on port 8787 is unaffected.

1. **Add material.** Drop files or paste a webpage URL and press Capture link. At least three separate episodes with usable text are needed to preserve whole-episode holdouts.
2. **Review.** Edit text, replace binary files, remove unwanted material or undo removal. Original bytes remain intact; training uses the working copies.
3. **Build.** Preparation, training, evaluation and export run as a background job. Activity shows errors and the most recent checkpoint. Stop/resume preserves completed saves.
4. **Try & export.** Enter a dialogue fragment. Download GGUF, Safetensors, tokenizer, Modelfile and evaluation reports. The model ZIP excludes source transcripts.

New projects use the **48M research preset** above. The quick-test preset uses about
1.6M parameters, 512-token windows and a train-only 4,096-token vocabulary. Neither
preset is a pretrained assistant, speech model or production podcast host. Source
timestamps are not measured speech pauses. Runtime checks and conversational quality
acceptance are separate.

## Input and compute

Text, structured text, subtitles, Word/documents, PDF, audio, video, images and UPOD use modality-specific adapters. Audio uses local Vosk. Images/scanned PDFs use local OCR; image/video descriptions use the configured local Ollama vision model and remain distinct from dialogue. Binary DOC requires Java on PATH and the bundled Tika JAR. Ordinary text ingestion and model training require neither Java nor Ollama.

Manual URL capture processes **one public HTML page per click**, preserving original HTML, extracted text, URL and checksums. It does not execute JavaScript, access private network services or follow links recursively. The source ZIP includes both the original extraction and current edited text.

Uploads: 256 MiB/file, 8 GiB of active material/project. Edits: 16 MiB. A source set locks when training starts to keep resumed weights tied to the same corpus. Projects live under `storage/` or `XOW_DATA`. Access keys are generated locally and are never shipped in packages. This is a **single-owner worker**, not multi-tenant hosting: everyone with its key can access its projects.

`XOW_DEVICE=auto` uses CUDA when available; `cpu` or `cuda` selects it explicitly. MPS/Apple GPU training is not implemented: macOS uses CPU. Intel Mac and Windows ARM acceptance are not claimed. CUDA requires a compatible PyTorch installation and driver. The tiny model may not benefit from a large GPU.

## Deployment packages

| Target | Deployment |
|---|---|
| Local computer | OS launcher above |
| Shared/static hosting, including GoDaddy | Upload the **shared-hosting ZIP contents** as a static site; connect it to an HTTPS compute worker |
| OVHcloud / other VPS | `docker compose up -d --build`; put HTTPS in front of local port 8788 |
| NVIDIA Docker worker | `docker compose -f compose.yaml -f compose.gpu.yaml up -d --build` |
| Runpod Pod | Use the GPU Dockerfile or a CUDA PyTorch Pod; run `python server.py --host 0.0.0.0 --port 8787`, expose HTTP port 8787 and persist `XOW_DATA` |

Shared hosting serves the canvas; the worker performs training. Set `XOW_ORIGINS=https://your-canvas.example` for a separately hosted UI. Configure proxy request limits for your uploads. Runpod provides HTTPS proxy URLs; see its [port configuration](https://docs.runpod.io/pods/configuration/expose-ports). CPU/GPU Docker templates are supplied; a CUDA execution claim requires actual GPU acceptance.

Optional `deploy/xputty-open-weight.service` is a systemd template for an administrator-managed Linux install. Create the `xputty` user, application directory and writable data directory before enabling it. `Caddyfile` is an HTTPS proxy template; set your domain and point it at the selected worker port.

## Source installation and builds

From a source checkout, install requirements and run `python tools/fetch_assets.py` to download checksum-pinned media assets. They are prebundled in full distribution ZIPs, not committed as binary Git history. Review `assets-manifest.json` and `THIRD-PARTY-NOTICES.txt`.

```
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
python tools/fetch_assets.py
python tools/build_packages.py --assets .
```

The builder uses a strict source allowlist. It excludes projects, credentials, `.venv`, logs, downloaded podcast captures, research weights and other archives. It sets executable ZIP permissions for shell launchers and emits SHA256 manifests. Runtime dependencies remain installed separately.

The GitHub repository contains the application under `Xputty_Open_Weight/`; its root workflow is copied from `ci/github-actions.yml`. No automatic deployment to a paid provider or public weight publication occurs.

## Verification

See `VERIFICATION.json` for actual tested scope, not inferred platform support. Tests cover authenticated ingestion, URL extraction, private-target rejection, editing/replacement/removal, immutable originals, source-set locking, training, evaluation, export, audition and checkpoint resume. HF tokenization/logit parity is required for completion. llama.cpp verification runs if installed (or `XOW_NATIVE_PYTHON` points to its Python). Ollama registration/generation runs when the loopback service is available; `XOW_OLLAMA_VERIFY=0` disables it.

The phase journal is SHA-linked and timestamped. It is not represented as a completed binary phase ledger or PyQoS implementation. The release does not embed Shadow Core weights or execute its router. User-provided research concepts remain separate from demonstrated capabilities.

Code follows the repository’s existing AGPL-3.0 license; see LICENSE. Third-party assets retain their respective licenses.


## GitHub Codespaces

The branch includes `.devcontainer/devcontainer.json`, pinned to Python 3.11.
For an existing Codespace, stop the worker, run `git pull --ff-only`, then use
**Ctrl+Shift+P → Codespaces: Rebuild Container**. Setup installs and verifies all
dependencies and media assets before starting the worker. A mismatched old `.venv`
is renamed to `.venv-backup-…`; project `storage/` is never removed.
The startup output includes a forwarded HTTPS URL with the access key already
in its fragment. Open that complete link to connect without manually copying the key.
Python 3.13/3.14 environments are rejected before installing training dependencies.
