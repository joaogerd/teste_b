from __future__ import annotations

import argparse
from pathlib import Path

from .validation.dataset import compare_datasets, write_diff_dataset
from .validation.report import render_table, write_markdown_report


def _split_variables(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    variables: list[str] = []
    for value in values:
        for item in value.split(","):
            item = item.strip()
            if item:
                variables.append(item)
    return variables or None


def compare_command(args) -> int:
    variables = _split_variables(args.variable)
    stats = compare_datasets(args.old, args.new, variables=variables)
    print()
    print("====================================================")
    print("Comparando NetCDF")
    print(f"OLD : {args.old}")
    print(f"NEW : {args.new}")
    print("====================================================")
    print(render_table(stats))
    print()

    diff_path = None
    if args.write_diff:
        diff_path = write_diff_dataset(args.old, args.new, args.write_diff, variables=variables)
        print(f"DIFF: {diff_path}")

    if args.report:
        report_path = write_markdown_report(
            args.report,
            stats,
            old_path=args.old,
            new_path=args.new,
            diff_path=diff_path,
        )
        print(f"REPORT: {report_path}")

    failed = [item for item in stats if item.status not in {"ok", "non_numeric"}]
    if failed and args.strict:
        return 2
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mpasverify",
        description="Ferramentas de validação e comparação de produtos NetCDF do workflow MPAS",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    compare = sub.add_parser("compare", help="Compara dois arquivos NetCDF e calcula estatísticas")
    compare.add_argument("--old", required=True, type=Path, help="Arquivo NetCDF de referência")
    compare.add_argument("--new", required=True, type=Path, help="Arquivo NetCDF novo")
    compare.add_argument(
        "-v",
        "--variable",
        action="append",
        help="Variável a comparar. Pode ser repetido ou usar lista separada por vírgula.",
    )
    compare.add_argument("--write-diff", type=Path, help="Escreve NetCDF com diferença new - old")
    compare.add_argument("--report", type=Path, help="Escreve relatório Markdown")
    compare.add_argument(
        "--strict",
        action="store_true",
        help="Retorna código 2 se houver variável ausente ou shape incompatível",
    )
    compare.set_defaults(func=compare_command)

    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
