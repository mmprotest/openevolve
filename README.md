# OpenEvolve

OpenEvolve is an end-to-end playground for evolving Python programs with large language
models. It combines long-context prompting, SQLite persistence, meta-prompt evolution,
and multi-objective selection so you can watch code improve generation after generation.
This README walks you through the whole system in painstaking detail—no prior experience
with evolutionary search, LLM tooling, or this repository is required.

---

## Table of contents

1. [Before you start](#before-you-start)
2. [Five minute quick start](#five-minute-quick-start)
3. [Running the Algorithmic Optimization demo](#running-the-algorithmic-optimization-demo)
4. [Using your own (or a local) OpenAI-compatible model](#using-your-own-or-a-local-openai-compatible-model)
5. [Understanding the architecture](#understanding-the-architecture)
6. [Configuration cheat sheet](#configuration-cheat-sheet)
7. [Inspecting results, artifacts, and logs](#inspecting-results-artifacts-and-logs)
8. [Troubleshooting & FAQ](#troubleshooting--faq)
9. [Developer workflow](#developer-workflow)
10. [License](#license)

---

## Before you start

Follow this checklist to ensure nothing surprises you later:

| Step | What you need to do | Why it matters |
| --- | --- | --- |
| 1 | Install **Python 3.11 or newer** (`python3 --version`). | Older interpreters miss required stdlib features. |
| 2 | Ensure **Git** is installed (`git --version`). | The engine checks out and rewinds files between generations. |
| 3 | Optionally export `OPENAI_API_KEY` and `OPENAI_BASE_URL`. | Needed if you plan to call a remote or self-hosted LLM. |
| 4 | Decide on a working directory with at least **1 GB** of free space. | Evolution writes logs, SQLite databases, and code snapshots per run. |

If any of the commands above fail, install the missing dependency before continuing.

---

## Five minute quick start

This is the fastest path from zero to seeing OpenEvolve mutate code. Every command is
copy-paste ready.

1. **Clone and enter the repository.**
   ```bash
   git clone https://github.com/mmprotest/openevolve.git
   cd openevolve
   ```

2. **Create and activate a virtual environment.**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install OpenEvolve in editable mode.**
   ```bash
   pip install -e .
   ```
   This pulls in the light dependency set (`pyyaml`, `tqdm`, and optional `matplotlib`).

4. **Initialize the SQLite database once.**
   ```bash
   openevolve init-db --db .openevolve/openevolve.db
   ```
   The command creates `.openevolve/` if it does not already exist and applies
   `src/openevolve/schema.sql`.

5. **Launch a canned two-generation demo run.**
   Make sure `OPENAI_API_KEY` (and optionally `OPENAI_BASE_URL`) are exported so the CLI can
   authenticate with your OpenAI-compatible endpoint.
   ```bash
   export OPENAI_API_KEY=sk-...
   openevolve run --config configs/demo_math.yml --run-id demo
   ```
   Expect the run to finish in under 30 seconds and write artifacts to `runs/demo/`.

6. **Inspect what just happened.**
   ```bash
   openevolve inspect --run-id demo --top 5
   openevolve export-archive --run-id demo --out artifacts/demo_archive.json
   openevolve viz --run-id demo --metric-axes accuracy,time_ms
   ```
   - `inspect` prints the top candidates and their metrics.
   - `export-archive` writes the Pareto archive as JSON for downstream analysis.
   - `viz` generates `artifacts/demo_pareto.png` (requires `matplotlib`).

7. **Resume the same run later.**
   ```bash
   openevolve resume --run-id demo
   ```
   The engine reads the last completed generation from the database and continues.

That’s it—you have run the full pipeline end to end.

---

## Running the Algorithmic Optimization demo

The repository ships with a multi-objective showcase that evolves a bubble sort baseline
toward faster, shorter insertion-style variants while preserving correctness. It highlights
Pareto optimisation across **accuracy**, **execution time**, and **code length**.

### Step-by-step

1. **Review the task definition.**
   - Source: `tasks/algorithmic_optimization/program.py`
   - Evaluators: `tasks/algorithmic_optimization/evaluate.py`
   - Config: `configs/algorithmic_optimization.yml`

2. **Execute the standalone example script (optional).**
   ```bash
   python examples/algorithmic_optimization.py
   ```
   The script spins up `EvolutionController` with the default OpenAI-compatible client,
   performs one evolutionary step, and prints baseline versus improved metrics.

3. **Run the evolutionary loop.**
   ```bash
   openevolve run --config configs/algorithmic_optimization.yml --run-id algo-demo
   ```
   Expect a longer run (several minutes) because evaluators measure runtime repeatedly.

4. **Inspect results and the Pareto front.**
   ```bash
   openevolve inspect --run-id algo-demo --top 10
   openevolve viz --run-id algo-demo --metric-axes accuracy,time_ms,code_size
   ```
   The `viz` command produces a scatter plot showing how candidates trade accuracy for
   speed and brevity. Check `runs/algo-demo/` for detailed logs, patches, and evaluator
   summaries per generation.

5. **Resume or branch off.**
   Use `openevolve resume --run-id algo-demo` to continue training, or copy the run
   directory and database entries to start a new variant with tweaked parameters.

### Verbose logging and troubleshooting

- Pass `--debug` to `examples/algorithmic_optimization.py` (or set `--log-level DEBUG`)
  to emit per-dataset diagnostics from both the evolution controller and the evaluation
  harness:
  ```bash
  python examples/algorithmic_optimization.py --debug
  ```
  The evaluator logs how each dataset was processed, the shape of the returned iterable,
  and whether the candidate satisfied the sorting contract—ideal for tracking down
  regressions when a run stalls.
- Implementations of `evolve_sort` **must return** the sorted sequence (for example by
  returning the mutated list). Returning `None` is treated as a contract violation and is
  now surfaced explicitly in the debug logs.

---

## Using your own (or a local) OpenAI-compatible model

OpenEvolve speaks the OpenAI Chat Completions protocol. You can point it to OpenAI’s
hosted endpoints or any self-hosted deployment that mimics the API (for example, vLLM,
Ollama, LM Studio, or Text Generation Web UI).

1. **Pick a configuration file.**
   Edit one of the YAML configs (e.g. `configs/default.yml`) and locate the `llm` block.

2. **Fill in the connection details.**
   ```yaml
   llm:
     mode: "openai"           # required to use the OpenAI REST protocol
     api_key: "sk-YOUR-KEY"   # omit to fall back on OPENAI_API_KEY env var
     base_url: "http://localhost:8000/v1"  # omit to use https://api.openai.com/v1
     model: "gpt-4.1-mini"    # replace with your deployed model ID
     temperature: 0.4
   ```

3. **(Optional) Configure via environment variables.**
   ```bash
   export OPENAI_API_KEY=sk-your-key
   export OPENAI_BASE_URL=http://localhost:8000/v1
   export OPENEVOLVE_MODEL_PRIMARY=gpt-4.1-mini
   ```
   CLI flags always override environment variables; environment variables override YAML
   defaults.

4. **Dry-run prompts without sending requests.**
   ```bash
   openevolve run --config configs/default.yml --run-id dry --dry-run
   ```
   The engine prints the assembled prompts so you can verify context length and
   instructions before contacting a real model.

If your deployment requires custom headers or authentication, wrap the engine yourself:
`openevolve.engine.evolve` accepts any callable `llm_call(prompt: str) -> str`, so you can
plug in bespoke networking logic.

---

## Understanding the architecture

OpenEvolve is composed of modular subsystems. Each can be used independently, but the CLI
wires everything together for you.

| Component | Module | Responsibility |
| --- | --- | --- |
| **ProgramDB** | `src/openevolve/db.py` | SQLite-backed storage for runs, candidates, evaluations, and meta-prompts. Auto-migrates using `src/openevolve/schema.sql`. |
| **PromptSampler** | `src/openevolve/prompt_sampler.py` | Builds long-context prompts that mix elite, novel, and failed exemplars while respecting token budgets. |
| **Meta-prompt evolution** | `src/openevolve/meta_prompt.py` | Maintains and mutates instruction templates; attributes fitness from downstream candidate performance. |
| **Apply engine** | `src/openevolve/apply.py` | Safely applies unified or JSON diffs to EVOLVE blocks or entire files, reverting on failure. |
| **Evaluator cascade** | `src/openevolve/evaluators/` | Runs pluggable evaluators in parallel with timeouts, retries, and optional early cancellation. |
| **Selection & archive** | `src/openevolve/selection.py` | Computes Pareto fronts, novelty scores, and ageing penalties; samples mixture populations for the next generation. |
| **Visualization** | `src/openevolve/viz.py` | Produces Pareto scatter plots and writes them to `artifacts/`. |
| **Engine** | `src/openevolve/engine.py` | Orchestrates the full evolution loop, handles persistence, and streams logging events. |
| **CLI** | `src/openevolve/cli.py` | User-facing entry point with `init-db`, `run`, `resume`, `inspect`, `export-archive`, and `viz` subcommands. |

Each generation flows through the following stages:

1. Select meta-prompt templates and parent candidates.
2. Assemble prompts with the PromptSampler and call the LLM.
3. Apply returned patches to the working tree (block-scoped or whole-file mode).
4. Persist candidates in SQLite and capture code snapshots.
5. Run evaluators via the cascade, respecting per-stage timeouts.
6. Update Pareto fronts, novelty scores, and ageing counters.
7. Attribute fitness back to meta-prompts and update the archive.
8. Emit JSONL logs and store artifacts under `runs/<run-id>/`.

---

## Configuration cheat sheet

All configuration files live in `configs/`. They are plain YAML and support comments.
Below is a condensed reference of the most frequently touched keys. When in doubt, copy
`configs/default.yml` and edit the values.

| Section | Key | Description |
| --- | --- | --- |
| `task` | `name`, `workdir`, `entrypoint`, `target_file`, `evolve_blocks` | Describes the optimisation problem, where code lives, and which EVOLVE blocks may be edited. |
| `population_size` | integer | Number of candidates generated per generation. |
| `generations` | integer | How many iterations to run. |
| `metrics` | mapping | Metric names mapped to `maximize`/`minimize`. Drives Pareto ranking. |
| `selection` | `elite`, `novel`, `young` | How many candidates of each category survive to seed the next generation. |
| `sampler` | `budget_tokens`, `elites_k`, `novel_m`, `include_failures` | Prompt assembly parameters. |
| `evolution` | `scope`, `apply_safe_revert` | Choose `blocks` or `wholefile`; enable automatic revert on failing tests. |
| `cascade` | `max_parallel`, `cancel_on_fail`, `evaluators` | Controls evaluator concurrency and definitions. |
| `meta_prompt` | `population`, `mutation_prob`, `selection_top_k` | Size and behaviour of the meta-prompt population. |
| `archive` | `capacity`, `k_novelty`, `ageing_threshold` | Archive and novelty search settings. |
| `llm` | `mode`, `api_key`, `base_url`, `model`, `temperature` | LLM connector configuration. Only `mode: openai` is supported. |
| `seed` | integer | Optional RNG seed for reproducibility. |

Whenever you edit a config file, rerun `openevolve run --config ...` or `resume` with the
same `run-id`. The engine persists the entire config JSON in the database for reproducible
runs.

---

## Inspecting results, artifacts, and logs

Everything generated during a run lives under `runs/<run-id>/`:

```
runs/
  <run-id>/
    config.json              # frozen config copy
    logs.jsonl               # line-delimited JSON events (generation, metrics, errors)
    meta_prompts/            # mutated templates per generation
    gen_<N>/
      prompts/               # assembled prompts fed to the LLM
      patches/               # JSON + unified diffs returned by the LLM
      snapshots/             # post-apply source files
      evaluations.json       # cascade outputs keyed by evaluator name
```

The SQLite database (`.openevolve/openevolve.db` by default) stores all persistent state:
runs, candidates, evaluations, and meta-prompt histories. Use any SQLite browser or the
CLI `inspect` command to explore it. For a structured export you can feed into notebooks,
run:

```bash
python scripts/export_archive.py --run-id demo --out artifacts/demo_archive.json
```

Visualisations land in `artifacts/`. If the directory is missing, commands such as
`openevolve viz` will create it automatically.

---

## Troubleshooting & FAQ

**The CLI says “command not found”.**  Make sure your virtual environment is activated
and that you installed the package with `pip install -e .`.

**Prompts look too long / I hit context limits.**  Lower `sampler.budget_tokens` or reduce
`sampler.elites_k` / `sampler.novel_m`. The sampler truncates the oldest examples first,
so keeping only the freshest elites helps.

**Evaluations never finish.**  Double-check the `timeout_s` values inside the `cascade`
section and that your evaluators are runnable in isolation (try `pytest` or the target
script manually).

**Whole-file mode reverted my patch.**  When `evolution.apply_safe_revert` is true, any
patch that fails to apply cleanly **or** causes evaluators to fail is undone. Inspect the
logs under `runs/<run-id>/gen_<N>/patches/` to see the diff and error message.

**I want to plug in a custom task.**  Add a directory under `tasks/` with three files:
`__init__.py`, `program.py` (with EVOLVE blocks), and `evaluate.py` (returning a metrics
dictionary). Point the config’s `task` section to those files. Use existing tasks as a
blueprint.

**Can I call the engine from Python directly?**  Yes:
```python
from openevolve import config, db, engine

cfg = config.load_config("configs/demo_math.yml")
program_db = db.ProgramDB(cfg["db_path"])
await engine.evolve(run_id="demo", cfg=cfg, llm_call=lambda prompt: "{\"diffs\": []}")
```
Remember to run this inside an async event loop (`asyncio.run`).

Still stuck? Open an issue with the command you ran, the config file you used, and the last
20 lines of `runs/<run-id>/logs.jsonl`. That information lets maintainers reproduce your
problem quickly.

---

## Developer workflow

Set up tooling once per clone:

```bash
pip install -e .[dev]  # optional extras: ruff, black, mypy, pytest
```

Before submitting patches, run the formatting and test suite:

```bash
ruff check src tests
black src tests
mypy src
pytest -q
```

The repository ships with unit tests for ProgramDB, selection, prompt sampling,
meta-prompt evolution, and the engine. They use deterministic fake LLM responses, so the
suite runs entirely offline.

---

## License

OpenEvolve is distributed under the MIT License. See `LICENSE` for full terms.
