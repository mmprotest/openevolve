# OpenEvolve

OpenEvolve is a research-oriented framework that explores large-language-model-driven evolutionary programming.  
The system focuses on evolving algorithmic building blocks inside explicit `EVOLVE` regions of source files.  
It combines structured prompting, diff-based editing, multi-stage evaluation cascades, and Pareto-guided search to 
progressively improve candidate programs.

## Features

- **LLM guided evolution** – structured prompts request SEARCH/REPLACE diffs that are applied to annotated blocks.
- **Configurable model endpoint** – works with OpenAI hosted models as well as local deployments (vLLM, Ollama, LM Studio) via an OpenAI-compatible REST interface.
- **Cascaded evaluation** – tasks may expose multiple evaluation stages to filter candidates with fast checks before expensive scoring.
- **Pareto dominance and novelty** – selection balances multi-objective optimization with behavioural diversity.
- **Safety aware sandbox** – candidate programs execute in a constrained subprocess with limited resources.
- **Plugin-style tasks** – new optimisation problems can be added under the `tasks/` directory.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Quickstart (offline demo)

You can exercise the full evolution loop without an API key by running the deterministic
demo. It copies the toy task into `runs/toy_sum_squares_demo.py`, applies a handcrafted diff,
and prints the resulting metrics and program.

```bash
python scripts/offline_demo.py
```

Example output:

```
Accepted metrics: {'correct': 1.0}
Updated program saved to: /path/to/openevolve/runs/toy_sum_squares_demo.py

--- Updated Program ---

"""Toy task for evolving sum of squares."""

from __future__ import annotations


def sum_of_squares(values: list[int]) -> int:
    """Compute the sum of squared elements."""

    # EVOLVE-BLOCK-START sum_of_squares
    return sum(value * value for value in values)
    # EVOLVE-BLOCK-END
```

## Running with a model endpoint

Set your API credentials (or point to a local OpenAI-compatible deployment) and start the
controller on one of the bundled tasks:

```bash
export OPENAI_BASE_URL=http://localhost:8000/v1
export OPENAI_API_KEY=sk-your-token
python scripts/run_controller.py --task speed_sort
```

All accepted candidates and evaluations are recorded in a SQLite database under `runs/`.
Inspect the archive to analyse Pareto fronts and metric history:

```bash
python scripts/inspect_db.py --db-path runs/speed_sort.sqlite
```

## Configuration reference

Environment variables follow the naming convention used by `pydantic` settings. The most
relevant options are:

| Variable | Description | Default |
| --- | --- | --- |
| `OPENAI_API_KEY` | API key for remote model providers. | `None` |
| `OPENAI_BASE_URL` | Base URL for the REST API. | `https://api.openai.com/v1` |
| `OPENEVOLVE_MODEL_PRIMARY` | Primary model identifier. | `gpt-4.1` |
| `OPENEVOLVE_MODEL_SECONDARY` | Optional secondary model for ensembles. | `gpt-4o-mini` |

Additional knobs such as concurrency and novelty thresholds can be found in
`openevolve.config.OpenEvolveSettings`.

## Tasks

Two demonstration tasks ship with the repository:

- `toy_sum_squares` – evolve a simple numerical routine.
- `speed_sort` – target faster array sorting heuristics.

Each task exposes an `evaluate` function returning a dictionary of metrics and can be extended with additional tests.

## Development

Run the formatting, linting, and test suite:

```bash
ruff check src tests
black src tests
mypy src
pytest
```

## License

The project is distributed under the terms of the MIT License.
