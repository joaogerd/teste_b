from __future__ import annotations

from pathlib import Path

from .statistics import VariableStats, format_number


COLUMNS = [
    ("variable", 28),
    ("status", 14),
    ("bias", 12),
    ("mae", 12),
    ("rmse", 12),
    ("rel_rmse", 12),
    ("max_abs", 12),
    ("corr", 12),
]


def render_table(stats: list[VariableStats]) -> str:
    header = (
        f"{'Variável':<{COLUMNS[0][1]}} "
        f"{'Status':<{COLUMNS[1][1]}} "
        f"{'Bias':>{COLUMNS[2][1]}} "
        f"{'MAE':>{COLUMNS[3][1]}} "
        f"{'RMSE':>{COLUMNS[4][1]}} "
        f"{'RelRMSE':>{COLUMNS[5][1]}} "
        f"{'MaxAbs':>{COLUMNS[6][1]}} "
        f"{'Corr':>{COLUMNS[7][1]}}"
    )
    sep = "-" * len(header)
    rows = [header, sep]
    for item in stats:
        rows.append(
            f"{item.name:<{COLUMNS[0][1]}} "
            f"{item.status:<{COLUMNS[1][1]}} "
            f"{format_number(item.bias):>{COLUMNS[2][1]}} "
            f"{format_number(item.mae):>{COLUMNS[3][1]}} "
            f"{format_number(item.rmse):>{COLUMNS[4][1]}} "
            f"{format_number(item.rel_rmse):>{COLUMNS[5][1]}} "
            f"{format_number(item.max_abs):>{COLUMNS[6][1]}} "
            f"{format_number(item.corr):>{COLUMNS[7][1]}}"
        )
    return "\n".join(rows)


def render_markdown(
    stats: list[VariableStats],
    *,
    old_path: str | Path,
    new_path: str | Path,
    diff_path: str | Path | None = None,
) -> str:
    lines = [
        "# MPAS verification report",
        "",
        f"- OLD: `{old_path}`",
        f"- NEW: `{new_path}`",
    ]
    if diff_path is not None:
        lines.append(f"- DIFF: `{diff_path}`")
    lines.extend(
        [
            "",
            "| Variable | Status | Bias | MAE | RMSE | RelRMSE | MaxAbs | Corr |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in stats:
        lines.append(
            "| "
            + " | ".join(
                [
                    item.name,
                    item.status,
                    format_number(item.bias),
                    format_number(item.mae),
                    format_number(item.rmse),
                    format_number(item.rel_rmse),
                    format_number(item.max_abs),
                    format_number(item.corr),
                ]
            )
            + " |"
        )
    notes = [item for item in stats if item.note]
    if notes:
        lines.extend(["", "## Notes", ""])
        for item in notes:
            lines.append(f"- `{item.name}`: {item.note}")
    return "\n".join(lines) + "\n"


def write_markdown_report(
    path: str | Path,
    stats: list[VariableStats],
    *,
    old_path: str | Path,
    new_path: str | Path,
    diff_path: str | Path | None = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_markdown(stats, old_path=old_path, new_path=new_path, diff_path=diff_path),
        encoding="utf-8",
    )
    return path
