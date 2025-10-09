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
pip install -e .
```

## Configuration

Environment variables follow the naming convention used by `pydantic` settings.  The most relevant options are:

| Variable | Description | Default |
| --- | --- | --- |
| `OPENAI_API_KEY` | API key for remote model providers. | `None` |
| `OPENAI_BASE_URL` | Base URL for the REST API. | `https://api.openai.com/v1` |
| `OPENEVOLVE_MODEL_PRIMARY` | Primary model identifier. | `gpt-4.1` |
| `OPENEVOLVE_MODEL_SECONDARY` | Optional secondary model for ensembles. | `gpt-4o-mini` |

Example local configuration:

```bash
export OPENAI_BASE_URL=http://localhost:8000/v1
export OPENAI_API_KEY=sk-local-placeholder
```

## Usage

Run the evolutionary controller against the bundled tasks:

```bash
python scripts/run_controller.py --task speed_sort
```

Inspect the on-disk database archive to monitor progress:

```bash
python scripts/inspect_db.py --db-path runs/speed_sort.sqlite
```

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
