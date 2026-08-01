"""Application-facing composition of integrated scene specifications."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from neuroglobe.integration.model import IntegratedSceneSpec


def resolve_gene_volume(gene: str, processed_data_dir: Path) -> Path:
    """Resolve a filtered gene volume without silently choosing ambiguity."""

    processed_data_dir = Path(processed_data_dir).resolve()
    preferred = (
        processed_data_dir / f"{gene}_filtered.nrrd",
        processed_data_dir / f"{gene.capitalize()}_filtered.nrrd",
    )
    for candidate in preferred:
        if candidate.is_file():
            return candidate

    expected_name = f"{gene}_filtered.nrrd".casefold()
    matches = sorted(
        path.resolve()
        for path in processed_data_dir.glob("*_filtered.nrrd")
        if path.name.casefold() == expected_name
    )
    if not matches:
        raise FileNotFoundError(f"Filtered expression volume not found for gene {gene!r}.")
    if len(matches) > 1:
        raise ValueError(f"Ambiguous filtered expression volumes for gene {gene!r}.")
    return matches[0]


def compose_selected_scene(
    *,
    projection_volume: Path,
    genes: Iterable[str],
    regions: Iterable[str],
    processed_data_dir: Path,
    repository_root: Path,
    output_spec: Path,
) -> IntegratedSceneSpec:
    """Create and save one GUI-selected integrated scene."""

    repository_root = Path(repository_root).resolve()
    output_spec = Path(output_spec).resolve()
    if output_spec.parent != repository_root:
        raise ValueError("Temporary integrated specifications must be in repository_root.")

    selected_genes = tuple(dict.fromkeys(gene.strip() for gene in genes if gene.strip()))
    if not selected_genes:
        raise ValueError("Select at least one gene-expression layer.")
    selected_regions = tuple(
        dict.fromkeys(region.strip() for region in regions if region.strip())
    )
    gene_volumes = {
        gene: resolve_gene_volume(gene, processed_data_dir)
        for gene in selected_genes
    }
    projection_volume = Path(projection_volume).resolve()
    if not projection_volume.is_file():
        raise FileNotFoundError(projection_volume)

    spec = IntegratedSceneSpec.compose(
        projection_volumes={projection_volume.stem: projection_volume},
        gene_expression_volumes=gene_volumes,
        regions=selected_regions,
        base_dir=repository_root,
    )
    spec.validate_sources()
    spec.save(output_spec)
    return spec
