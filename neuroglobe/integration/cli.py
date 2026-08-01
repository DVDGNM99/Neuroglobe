"""Command-line composition, validation, and rendering of integrated scenes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

from neuroglobe.core.provenance import write_json_immutable
from neuroglobe.integration.model import IntegratedSceneSpec


def _named_paths(values: Iterable[str], *, option: str) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"{option} requires LABEL=PATH, received {value!r}.")
        label, raw_path = value.split("=", 1)
        label = label.strip()
        if not label or not raw_path.strip():
            raise ValueError(f"{option} requires a non-empty LABEL and PATH.")
        if label in parsed:
            raise ValueError(f"Duplicate {option} label: {label}")
        parsed[label] = Path(raw_path).resolve()
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neuroglobe-integrated-viewer",
        description=(
            "Compose, validate, and render projection plus gene-expression "
            "volumes in a shared Allen CCF physical frame."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    compose = subparsers.add_parser("compose", help="create a checksummed scene spec")
    compose.add_argument("--output", type=Path, required=True)
    compose.add_argument(
        "--projection",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help="projection NRRD layer; repeat for multiple volumes",
    )
    compose.add_argument(
        "--gene",
        action="append",
        default=[],
        metavar="GENE=PATH",
        help="gene-expression NRRD layer; repeat for multiple genes",
    )
    compose.add_argument(
        "--region",
        action="append",
        default=[],
        metavar="ACRONYM",
        help="reference brain region; repeat for multiple regions",
    )
    compose.add_argument("--atlas", default="allen_mouse_25um")

    validate = subparsers.add_parser("validate", help="verify schema, files, and geometry")
    validate.add_argument("spec", type=Path)

    render = subparsers.add_parser("render", help="validate and open one integrated scene")
    render.add_argument("spec", type=Path)
    render.add_argument(
        "--non-interactive",
        action="store_true",
        help="request a non-interactive render (primarily for headless smoke tests)",
    )
    render.add_argument("--no-legend", action="store_true")
    render.add_argument(
        "--manifest-out",
        type=Path,
        help="immutable run manifest path (default includes a unique run UUID)",
    )
    return parser


def _compose(args: argparse.Namespace) -> int:
    output = args.output.resolve()
    spec = IntegratedSceneSpec.compose(
        atlas_name=args.atlas,
        regions=args.region,
        projection_volumes=_named_paths(args.projection, option="--projection"),
        gene_expression_volumes=_named_paths(args.gene, option="--gene"),
        base_dir=output.parent,
    )
    spec.validate_sources()
    spec.save(output)
    print(f"Integrated scene written: {output}")
    print(f"Scene ID: {spec.scene_id}")
    return 0


def _validate(args: argparse.Namespace) -> int:
    spec = IntegratedSceneSpec.load(args.spec, validate_sources=True)
    print(
        f"Valid integrated scene {spec.scene_id}: "
        f"{len(spec.layers)} layers on {spec.atlas_name}."
    )
    return 0


def _render(args: argparse.Namespace) -> int:
    from neuroglobe.integration.rendering import IntegratedRenderEngine

    spec_path = args.spec.resolve()
    spec = IntegratedSceneSpec.load(spec_path, validate_sources=True)
    result = IntegratedRenderEngine(spec).render(
        interactive=not args.non_interactive,
        show_legend=not args.no_legend,
        validate_sources=False,
    )
    if not result.success:
        details = "; ".join(result.errors + result.warnings) or "no layers rendered"
        raise RuntimeError(f"Integrated render failed: {details}")
    manifest = spec.build_run_manifest()
    manifest_path = (
        args.manifest_out.resolve()
        if args.manifest_out
        else spec_path.with_name(
            f"{spec_path.stem}.{manifest['run_id']}.run.json"
        )
    )
    write_json_immutable(manifest_path, manifest)
    print(
        f"Rendered {result.projections_rendered} projection and "
        f"{result.genes_rendered} gene-expression layers."
    )
    print(f"Run manifest written: {manifest_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "compose":
            return _compose(args)
        if args.command == "validate":
            return _validate(args)
        if args.command == "render":
            return _render(args)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
