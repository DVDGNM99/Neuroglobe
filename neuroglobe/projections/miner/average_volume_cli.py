"""CLI for registered-volume manifests and average-brain statistics."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from neuroglobe.integration.geometry import read_nrrd_geometry
from neuroglobe.projections.miner.average_export import (
    AVERAGE_STATISTICS,
    export_average_nrrd,
)
from neuroglobe.projections.miner.average_volume import (
    AverageVolumeProtocol,
    RegistrationQuality,
    aggregate_registered_volumes,
    create_registered_volume_manifest,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neuroglobe-average-volume",
        description=(
            "Create registration contracts and compute bounded-memory "
            "voxel-wise mean, variance, and 95% confidence intervals."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    register = subparsers.add_parser(
        "register",
        help="bind a registered .npy array to transform, geometry, and QC",
    )
    register.add_argument("volume", type=Path)
    register.add_argument("--transform", type=Path, required=True)
    register.add_argument("--geometry-nrrd", type=Path, required=True)
    register.add_argument("--output", type=Path, required=True)
    register.add_argument("--subject-id", required=True)
    register.add_argument("--atlas", required=True)
    register.add_argument("--reference-id", required=True)
    register.add_argument("--method", required=True)
    register.add_argument("--interpolation", default="linear")
    register.add_argument("--dice", type=float, required=True)
    register.add_argument("--hausdorff-um", type=float, required=True)
    register.add_argument("--landmark-rmse-um", type=float, required=True)

    aggregate = subparsers.add_parser(
        "aggregate",
        help="aggregate registered subjects that pass QC",
    )
    aggregate.add_argument("manifests", nargs="+", type=Path)
    aggregate.add_argument("--output-dir", type=Path, required=True)
    aggregate.add_argument("--prefix", default="average_projection")
    aggregate.add_argument("--min-subjects", type=int, default=2)
    aggregate.add_argument("--min-dice", type=float, default=0.8)
    aggregate.add_argument("--max-hausdorff-um", type=float, default=500.0)
    aggregate.add_argument("--max-landmark-rmse-um", type=float, default=250.0)
    aggregate.add_argument("--working-memory-mib", type=float, default=64.0)
    aggregate.add_argument("--allow-negative", action="store_true")
    aggregate.add_argument(
        "--output-dtype",
        choices=("float32", "float64"),
        default="float32",
    )

    export = subparsers.add_parser(
        "export-nrrd",
        help="stream one verified average statistic to physical-space NRRD",
    )
    export.add_argument("manifest", type=Path)
    export.add_argument("--statistic", choices=AVERAGE_STATISTICS, default="mean")
    export.add_argument("--output", type=Path, required=True)
    return parser


def _register(args: argparse.Namespace) -> int:
    output = create_registered_volume_manifest(
        volume_path=args.volume,
        transform_path=args.transform,
        manifest_path=args.output,
        subject_id=args.subject_id,
        atlas_name=args.atlas,
        reference_id=args.reference_id,
        method=args.method,
        interpolation=args.interpolation,
        quality=RegistrationQuality(
            dice=args.dice,
            hausdorff_um=args.hausdorff_um,
            landmark_rmse_um=args.landmark_rmse_um,
        ),
        geometry=read_nrrd_geometry(args.geometry_nrrd),
    )
    print(f"Registered-volume manifest written: {output}")
    return 0


def _aggregate(args: argparse.Namespace) -> int:
    protocol = AverageVolumeProtocol(
        min_subjects=args.min_subjects,
        min_dice=args.min_dice,
        max_hausdorff_um=args.max_hausdorff_um,
        max_landmark_rmse_um=args.max_landmark_rmse_um,
        require_nonnegative=not args.allow_negative,
        output_dtype=args.output_dtype,
    )

    def report_progress(current: int, total: int) -> None:
        print(f"PROGRESS|{current}|{total}", flush=True)

    result = aggregate_registered_volumes(
        args.manifests,
        output_dir=args.output_dir,
        output_prefix=args.prefix,
        protocol=protocol,
        maximum_working_bytes=int(args.working_memory_mib * 1024 * 1024),
        progress_callback=report_progress,
    )
    print(f"Included subjects: {', '.join(result.included_subjects)}")
    if result.excluded:
        print(
            "Excluded subjects: "
            + ", ".join(item.subject_id for item in result.excluded)
        )
    print(f"Mean volume: {result.mean_path}")
    print(f"Run manifest: {result.manifest_path}")
    return 0


def _export_nrrd(args: argparse.Namespace) -> int:
    def report_progress(current: int, total: int) -> None:
        print(f"PROGRESS|{current}|{total}", flush=True)

    result = export_average_nrrd(
        args.manifest,
        statistic=args.statistic,
        output_path=args.output,
        progress_callback=report_progress,
    )
    print(f"NRRD volume: {result.nrrd_path}")
    print(f"Artifact manifest: {result.manifest_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "register":
            return _register(args)
        if args.command == "aggregate":
            return _aggregate(args)
        if args.command == "export-nrrd":
            return _export_nrrd(args)
    except (FileExistsError, FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
