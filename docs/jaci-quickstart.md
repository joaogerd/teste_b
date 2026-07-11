# JACI quick start

This page gives the command sequence used for the validated global `x1.10242`
case on JACI.

## 1. Load the environment

```bash
cd /p/projetos/monan_das/joao.gerd/projects/teste_b
source /p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global/scripts/load_jaci_env.sh
```

Set the standard inputs:

```bash
CONFIG=configs/jaci-x1.10242.yaml
BFLOW=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/bflow_preprocessing/np128_2026062200_2026062500
```

## 2. Check the resolved configuration

```bash
PYTHONPATH="src:${PYTHONPATH:-}" python -m bmatrix check-config \
  --config "$CONFIG"
```

## 3. Run selected stages

Only UNBALANCE:

```bash
PYTHONPATH="src:${PYTHONPATH:-}" python -m bmatrix build \
  --config "$CONFIG" \
  --bflow-workspace "$BFLOW" \
  --from-stage unbalance \
  --to-stage unbalance \
  --clean \
  --poll-seconds 10
```

UNBALANCE through HDIAG:

```bash
PYTHONPATH="src:${PYTHONPATH:-}" python -m bmatrix build \
  --config "$CONFIG" \
  --bflow-workspace "$BFLOW" \
  --from-stage unbalance \
  --to-stage hdiag \
  --clean \
  --poll-seconds 10
```

NICAS only after HDIAG is valid:

```bash
PYTHONPATH="src:${PYTHONPATH:-}" python -m bmatrix build \
  --config "$CONFIG" \
  --bflow-workspace "$BFLOW" \
  --from-stage nicas \
  --to-stage nicas \
  --clean \
  --poll-seconds 10
```

SO only after NICAS is valid:

```bash
PYTHONPATH="src:${PYTHONPATH:-}" python -m bmatrix build \
  --config "$CONFIG" \
  --bflow-workspace "$BFLOW" \
  --from-stage so \
  --to-stage so \
  --clean \
  --poll-seconds 10 \
  2>&1 | tee /p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/audits/so_latest.log
```

DIRAC only after SO and NICAS are valid:

```bash
PYTHONPATH="src:${PYTHONPATH:-}" python -m bmatrix build \
  --config "$CONFIG" \
  --bflow-workspace "$BFLOW" \
  --from-stage dirac \
  --to-stage dirac \
  --clean \
  --poll-seconds 10 \
  2>&1 | tee /p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/audits/dirac_latest.log
```

Full workflow through DIRAC:

```bash
PYTHONPATH="src:${PYTHONPATH:-}" python -m bmatrix build \
  --config "$CONFIG" \
  --bflow-workspace "$BFLOW" \
  --clean \
  --poll-seconds 10
```

Full workflow through plots:

```bash
PYTHONPATH="src:${PYTHONPATH:-}" python -m bmatrix build \
  --config "$CONFIG" \
  --bflow-workspace "$BFLOW" \
  --to-stage plots \
  --plot-level 30 \
  --plot-dpi 150 \
  --clean \
  --poll-seconds 10
```

## 4. Validate completed products

```bash
PYTHONPATH="src:${PYTHONPATH:-}" python -m bmatrix validate \
  --config "$CONFIG" \
  --bflow-workspace "$BFLOW" \
  --stage so

PYTHONPATH="src:${PYTHONPATH:-}" python -m bmatrix validate \
  --config "$CONFIG" \
  --bflow-workspace "$BFLOW" \
  --stage dirac
```

## 5. Generate plots only

```bash
PYTHONPATH="src:${PYTHONPATH:-}" python -m bmatrix plots \
  --config "$CONFIG" \
  --bflow-workspace "$BFLOW" \
  --plot-level 30 \
  --plot-dpi 150 \
  --clean
```

## 6. Development checks

Always run:

```bash
TMPDIR=/p/projetos/monan_das/joao.gerd/projects/teste_b/.pytest-tmp \
PYTHONPATH="src:${PYTHONPATH:-}" \
python -m pytest -p no:cacheprovider -q

python -m ruff check src/bmatrix tests

git diff --check
```

Avoid writing persistent audit files to `/tmp`. Use:

```text
/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/audits/
```
