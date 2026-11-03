# Torch cu130 and setuptools adversarial review

Date: 2026-11-03
Branch under review: fix/torch-cu130-setuptools (uncommitted)
Reviewer role: independent adversarial gate

Only this report may be created or appended. No implementation/test edits, installs, commits, pushes, PRs, or paid model calls are authorized for this review. Prior reported successes are supplied evidence until independently inspected or reproduced. Warnings remain visible. A passing smoke check does not establish universal compatibility.

## Checklist

- [ ] A. Compare HEAD and live manifest/lock by package, version, source and platform marker; verify the intended Torch/torchvision/setuptools pairing and detect unrelated changes.
- [ ] B. Verify actual interpreter, GPU, driver, architecture and CUDA execution, including operations beyond matrix multiplication.
- [ ] C. Inspect cached model loading and execute a bounded real 2025 race/inference path with LLM calls disabled.
- [ ] D. Challenge HF cache/Whisper, CUDA RAG embedding, TorchVision NMS and Lightning training; distinguish smoke coverage from upstream support.
- [ ] E. Reconcile removed OSV exceptions against installed/locked versions and advisory ranges; inspect remaining Pillow/Arcade constraints.
- [ ] F. Check documentation and Dependabot routing against source markers; verify the Telemetry submodule boundary.
- [ ] Record file/line evidence, severity, remaining breakage, failed attack attempts and unexecuted routes, including Python 3.12 GPU and Lightning 2.6 upstream coverage.

## Supplied evidence awaiting independent review

The handoff reports 1,629 Python 3.11 pytest passes, Ruff/mypy passes, a complete no-LLM Lusail 2025 simulation, a CUDA RAG query, CUDA kernels/NMS and a one-batch Lightning fit. Python 3.12 GPU has not been run locally; planned CPU CI cannot establish that route. Telemetry retains its independent cu128 pin.

## Verified findings recorded during review

### LOW F1. The testing guide still reports the resolved setuptools issue as blocked

`docs/pages/testing.md:170-175` says the latest local audit finds setuptools 81.0.0 and that Arcade/CUDA graphs constrain its fix. The candidate lock resolves setuptools 84.2.1, and the independently inspected Python 3.11 candidate environment has that exact version. The CUDA constraint has been removed by Torch 2.13.0. This paragraph gives a false current reason to retain the setuptools exception. Update the current dependency statement and label any historical count as historical. No application failure was demonstrated by this documentation defect.

## Independent execution evidence

### A. Initial lock and scope comparison

Review base is HEAD `18c6fd0671040beb65e85f15ec5d389adc50ff10`. Parsed both HEAD and the live `uv.lock` with Python 3.11 `tomllib`, grouped every package by name/version/source, and compared all groups. Exactly three package names changed: setuptools 81.0.0 -> 84.2.1; Torch Windows 2.11.0+cu128 and non-Windows 2.12.0[+cpu] -> 2.13.0 variants; torchvision Windows 0.26.0+cu128 and non-Windows 0.27.0[+cpu] -> 0.28.0 variants. No other package version or registry source shifted.

The manifest uses a compatible minor range, not an exact version pin (`pyproject.toml:27-28`); the committed lock candidate fixes the exact pair. Windows source markers select cu130 and non-Windows markers select the CPU index (`pyproject.toml:170-196`). Python 3.11 and 3.12 Windows x64 wheel records are present. Mac arm64 versions omit the `+cpu` local suffix while still coming from the CPU index. That is not an unintended GPU selection.

### B. Independent Windows CUDA execution

Used existing `.venv-py311-check/Scripts/python.exe -B`, Python 3.11.14, without installing or syncing packages. The normal `.venv` still reports Python 3.10.19; it was not mistaken for the candidate environment. Candidate imports report Torch 2.13.0+cu130, torchvision 0.28.0+cu130, setuptools 84.2.1 and CUDA runtime 13.0. `nvidia-smi` independently reports RTX 5070 Laptop GPU, driver 617.42, compute capability 12.0; Torch lists `sm_120`.

Reproduced CUDA matmul, convolution and scaled dot product attention and compared their outputs to CPU on the same inputs with explicit tolerances (matmul 2e-4, convolution/attention 1e-4 absolute and relative). Backpropagation produced the expected gradient `2*x`. Real CUDA torchvision NMS retained boxes [0, 2] as expected. `torch.utils.cpp_extension.BuildExtension` imports with setuptools 84.2.1. These passed; compiling a native extension was not exercised. No warnings were filtered.

## Risks identified in the initial review

### MEDIUM R1. Windows Python 3.12 GPU compatibility (closed in follow-up)

**Status: CLOSED on 2026-11-03.** Follow-up verification below ran the full locked install, CUDA operations, cached-model inference, RAG, Whisper, and the full test suite under Windows Python 3.12.12.

`pyproject.toml:11` supports both Python 3.11 and 3.12. The Windows source markers at `pyproject.toml:189-196` apply to both; `uv.lock:4775-4795` and `uv.lock:4854-4874` select the new CUDA pair. The local executed checks used Python 3.11.14 only. `.github/workflows/ci.yml:63,101-105` runs both Python versions on the Linux test job and therefore resolves CPU packages, not Windows cu130 packages. A green CPU matrix cannot establish DLL loading, CUDA kernels, torchvision native operators or cached model deserialization on Windows Python 3.12.

At the initial review this was a coverage gap, not an observed Python 3.12 failure. The follow-up below closes that gap with the actual candidate environment.

### MEDIUM R2. Lightning 2.6.6 is outside the upstream Torch CI coverage

`pyproject.toml:27-29` admits Torch 2.13 with Lightning, while `uv.lock:3673-3674` fixes pytorch-lightning to 2.6.6. The [official Lightning compatibility matrix](https://lightning.ai/docs/pytorch/stable/versioning.html#compatibility-matrix), inspected on 2026-11-03, lists Torch 2.10 as the last CI-tested version for Lightning 2.6. The document says this is informational rather than a hard upper bound. It does not establish incompatibility, but it also does not officially cover Torch 2.13.

The one-batch GPU Trainer fit covers neither the project's full training cycle nor checkpoint save/resume, validation loops, mixed precision or distributed training. The follow-up below independently passed that smoke on Python 3.12, but the upstream coverage gap and full-training limitation remain. Do not claim full training compatibility from the smoke fit. Validate the actual training workflow and checkpoints before relying on this combination for model training.

## Scope and exception reconciliation

### E. Exception removal is supported for the frozen root lock

Parsed HEAD and live `osv-scanner.toml`. Exactly three exception records were removed, including the two setuptools records; it is not five removals. No surviving exception changed and no new exception was added. The candidate has 58 remaining records.

| Removed record | Reason supported by inspected evidence |
| --- | --- |
| GHSA-rrmf-rvhw-rf47 | All root Torch variants resolve to 2.13.0 (`uv.lock:4725-4795`). The [GitHub reviewed advisory](https://github.com/advisories/GHSA-rrmf-rvhw-rf47) identifies 2.13.0 as patched. |
| PYSEC-2026-3447 | Root setuptools resolves to 84.2.1 (`uv.lock:4287-4288`), above the fixed 83.0.0. The [upstream advisory record](https://raw.githubusercontent.com/pypa/advisory-database/main/vulns/setuptools/PYSEC-2026-3447.yaml) identifies that fixed version. |
| GHSA-xmj3-9gf7-h52w | 84.2.1 is above the fixed 84.1.0 in the [setuptools advisory](https://github.com/pypa/setuptools/security/advisories/GHSA-xmj3-9gf7-h52w). |

The installed Torch metadata declares `setuptools>=77.0.3`, with no `<82` cap. Installed Arcade metadata still requires `pillow~=11.3.0`; the root lock retains Arcade 3.3.3 (`uv.lock:179-180`) and Pillow 11.3.0 (`uv.lock:3008-3009`). The remaining Pillow reasons describing the stable Arcade `<11.4` constraint remain accurate. A valid reason for a temporary exception does not mean the vulnerability is fixed. This audit did not run a fresh complete OSV scan or query current Dependabot counts.

Tornado and filelock changes precede this diff: HEAD history includes merged PRs #1368 and #1369. Their versions are unchanged by this candidate. This report does not attribute their earlier fixes to the Torch change.

### F. Source routing and submodule boundary

The edited `.github/dependabot.yml:15-19` comment matches Windows cu130 and CPU elsewhere. `docs/pages/ci-cd.md:188` correctly refers to cu130 Windows and the matched pair. The manifest source comments at `pyproject.toml:170-196` also match the actual markers. The inspected GRIDMIND design diff updates the root Windows environment to cu130; its separate training environment is still explicitly separate. The stale testing-guide statement is LOW finding F1 above.

The Telemetry gitlink is `a34e23f0de43fe0dba612b56cf91a46f7cf00c09`, and its working tree was clean when inspected. Neither the gitlink nor any Telemetry file appears in the root diff. Its own `pyproject.toml` still selects the cu128 index for Windows; its lock retains Torch 2.11.0+cu128 and setuptools 81.0.0 (`src/telemetry/uv.lock:2913-2918,3136-3154`). This is a separate environment and separate security state. Root exception removal must not be described as fixing Telemetry. No submodule files were edited.

## Attempted execution and explicit limits

The user requested a wrap-up before further probes. No additional routes were started after that request.

- Independently executed the GPU parity/backward/NMS/BuildExtension probes described under B. They passed in the existing candidate environment.
- Attempted the actual `scripts.f1_sim` Lusail/NOR/McLaren 2025 route with `--no-llm --no-real-radios --no-first-run --radio-every 10 --verbose`, offline HF settings and a process audit hook denying file writes and network connections. The first attempt stopped on the Windows null device; the second allowed that non-file device but stopped during Torch's dill import when Python's temporary-directory discovery attempted file writes. Those writes were rejected before execution. The process did not reach model inference. This is a limitation imposed by the audit's report-only write boundary, not evidence that the ordinary CLI fails. There is no independently reproduced 57-lap result from this review.
- Inspected the real no-LLM dispatch (`src/strategy/inference/engine.py:171-176`) and agent calls (`src/strategy/inference/no_llm.py:268-285`). The route runs pace, tire, situation and radio, and deliberately skips the LLM-backed pit/RAG agents. A no-LLM race run alone cannot verify the RAG query route.
- Inspected cached TCN bundle loading at `src/agents/tire_agent.py:422-442`. It deserializes the real bundles with `weights_only=False` and maps them to CPU. This audit did not independently load those bundles or compare numerical predictions against the previous Torch version. Successful CUDA tensor probes cannot substitute for that comparison, and successful CPU TCN inference cannot be presented as GPU TCN coverage.
- Inspected Whisper's production model load and audio decode/transcription path at `src/nlp/radio_runner.py:117-180`; local Whisper checkpoints are present. Did not independently transcribe a real audio clip. Synthetic radios skip Whisper and therefore do not validate it.
- Inspected RAG construction and encoding at `src/rag/retriever.py:243-256,296-308`. The local manifest describes BGE-M3 with 1024 dimensions. Did not independently execute CUDA embeddings or open/query the disk Qdrant store under the report-only write constraint. The supplied successful three-article 2025 query remains supplied evidence.
- Did not rerun the 1,629-case pytest suite, Ruff, mypy, Lightning fit, actual project training/checkpoint resume, full GUI/Arcade/PITWALL/backend workflows, native-extension compilation or Python 3.12 GPU. Their earlier supplied results are not relabeled as independent execution. No fresh remote CI result was inspected for this uncommitted candidate.
- No package installs, model downloads, paid LLM calls, implementation/test changes, commits, pushes or PR actions were performed. Only this report was intentionally written.

## What I tried to break and could not

1. Found no unrelated package-version or registry-source movement by comparing every package in the full HEAD and live locks.
2. Found no unintended Windows/CPU pairing in the inspected root manifest and resolved package records. Both supported Python versions have Windows x64 wheel records for the selected pair.
3. Could not break the actual Python 3.11 cu130 runtime with same-input CPU/CUDA parity probes for matmul, convolution and attention, an analytic-gradient check or a known-result CUDA NMS case.
4. Could not reproduce a setuptools BuildExtension import failure with installed 84.2.1; did not infer that native compilation therefore works.
5. Could not refute the three exception removals against the frozen versions and inspected published fixed ranges. Pillow's remaining Arcade constraint still exists.
6. Found no Telemetry mutation in the candidate diff or inspected submodule status.

## Checklist outcome

- [x] A reviewed. Exact frozen pair and absence of unrelated version/source changes verified; manifest ranges allow later patch releases.
- [x] B reviewed and independently executed on Windows Python 3.11.14 / RTX 5070 Laptop / driver 617.42.
- [x] C reviewed. Relevant source inspected; independent CLI repetition stopped at the report-only filesystem boundary before inference. The supplied full-race result was not independently reproduced.
- [x] D reviewed. CUDA NMS independently passed; HF/Whisper, CUDA RAG and Lightning execution remain supplied evidence rather than independently reproduced checks. Lightning upstream coverage limitation recorded.
- [x] E reviewed. Three total removal records are supported for this root lock; Pillow exceptions still have the declared Arcade constraint.
- [x] F reviewed. Edited routing comments match; testing-guide drift found; submodule boundary preserved.
- [x] File/line references, severity, unresolved routes and unsuccessful attack attempts recorded.

## Initial gate result

No HIGH or blocking runtime regression was reproduced by the completed probes. This is not an unconditional compatibility clearance. Two MEDIUM risks remain: Windows Python 3.12 GPU execution is unverified, and Lightning 2.6.6 has no published Torch 2.13 CI coverage. One LOW current-documentation defect is confirmed. C and most of D retain the supplied execution evidence without an independent reproduction in this review.

Follow-up items from the initial review:

1. **Completed:** run the Windows Python 3.12 GPU/model path. The PR's Linux CPU matrix is also green.
2. **Open limitation:** validate full training and checkpoint resume before claiming full training compatibility.
3. **Completed:** correct `docs/pages/testing.md:170-175` so it no longer describes setuptools as blocked.
4. Keep root and Telemetry results separate when reporting security closure. No exception removal here closes the submodule's remaining independent vulnerable resolution.

## Follow-up verification

Executed after the initial audit on 2026-11-03 under both Windows Python runtimes:

- The full repository test suite passed on Python 3.11.14 and 3.12.12: 1,710 tests per runtime (227 warnings on 3.11; 9 on 3.12).
- PyTorch 2.13.0+cu130 ran convolution, scaled dot-product attention, backward propagation, and a CUDA torchvision NMS call on the RTX 5070 Laptop GPU with driver 617.42.
- One-batch Lightning CUDA training completed on Python 3.11 and 3.12. This is a smoke check, not validation of the training notebooks or checkpoint resume.
- The full 57-lap Lusail simulation completed on both runtimes with cached models, offline Hugging Face access, synthetic radio events, and LLM synthesis disabled.
- Real Whisper turbo transcription completed from cached 2025 radio audio in offline mode on both runtimes.
- CUDA BGE-M3 queries against local Qdrant returned only 2025 sporting-regulation results on both runtimes. The client closed before process exit.
- Ruff check, Ruff format, mypy, frozen lock validation, and frozen dependency sync passed.
- The setuptools/PyTorch/vision lock resolves to 84.2.1, 2.13.0+cu130, and 0.28.0+cu130 on Windows. CPU variants resolve to 2.13.0+cpu and 0.28.0+cpu. One Torch and two setuptools OSV exceptions were removed.
- The current stable Arcade 3.3.3 Pillow constraint remains unchanged, so Pillow advisories remain open. The Telemetry submodule retains its separate cu128 manifest.

## Current status and residual risk

No runtime failure was reproduced in the tested Windows Python 3.11 or 3.12 paths. The full project training notebooks and checkpoint save/resume were not run; Lightning 2.6.6's published compatibility matrix still stops at Torch 2.10. CI has not yet run on this uncommitted candidate. The Pillow upgrade remains blocked by the stable Arcade pin.
