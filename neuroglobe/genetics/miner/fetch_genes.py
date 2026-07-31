import json
import shutil
import tempfile
import traceback
import urllib.request
import zipfile
from pathlib import Path

import SimpleITK as sitk
from allensdk.api.queries.rma_api import RmaApi
from allensdk.api.queries.grid_data_api import GridDataApi

from neuroglobe.core.provenance import artifact_manifest, write_json_atomic
from neuroglobe.genetics.definitions import (
    RAW_DATA_DIR,
    CONFIGS_DIR,
    ensure_runtime_directories,
)


def _safe_extract(archive: Path, destination: Path) -> None:
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            member_path = (destination / member.filename).resolve()
            try:
                member_path.relative_to(destination_root)
            except ValueError as error:
                raise ValueError(
                    f"Unsafe archive member path: {member.filename}"
                ) from error
        bundle.extractall(destination)


def _download_archive(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Neuroglobe/5.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        with destination.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)


def fetch_all_genes() -> bool:
    manifest_path = CONFIGS_DIR / "manifest.json"

    with open(manifest_path, 'r') as f:
        manifest = json.load(f)

    genes = manifest.get("processing", {}).get("genes", [])

    if not genes:
        print("[ERROR] No genes found in manifest.")
        return False

    rma = RmaApi()
    grid_api = GridDataApi()

    print(f"Starting fetch for {len(genes)} genes...")
    all_succeeded = True

    for gene in genes:
        output_nrrd = RAW_DATA_DIR / f"{gene}_density.nrrd"

        if output_nrrd.exists():
            print(f"[INFO] Data for {gene} already exists. Skipping download.")
            continue

        print(f"--- Fetching {gene} ---")
        try:
            datasets = rma.model_query('SectionDataSet', criteria=f"products[id$eq1],genes[acronym$eq'{gene}']")

            if isinstance(datasets, list) and len(datasets) > 0:
                success_for_gene = False
                for ds in datasets:
                    dataset_id = ds['id']
                    print(f"[{gene}] Trying dataset ID: {dataset_id}")

                    # Fetch raw zip via Direct Allen API
                    download_url = f"https://api.brain-map.org/grid_data/download_file/{dataset_id}?image=density"
                    print(f"[{gene}] Downloading from {download_url}...")
                    with tempfile.TemporaryDirectory(
                        prefix=f"{gene}_{dataset_id}_", dir=RAW_DATA_DIR
                    ) as temporary_name:
                        temporary_dir = Path(temporary_name)
                        archive_path = temporary_dir / "density.zip"
                        try:
                            _download_archive(download_url, archive_path)
                            _safe_extract(archive_path, temporary_dir)
                            print(f"[{gene}] Downloaded and safely extracted archive.")
                        except Exception as error:
                            print(
                                f"[{gene}] Direct download failed: {error}. "
                                "Trying GridDataApi..."
                            )
                            try:
                                grid_api.download_gene_expression_grid_data(
                                    dataset_id, "density", str(archive_path)
                                )
                                if archive_path.exists() and zipfile.is_zipfile(archive_path):
                                    _safe_extract(archive_path, temporary_dir)
                            except Exception as fallback_error:
                                print(
                                    f"[{gene}] GridDataApi fallback failed: "
                                    f"{fallback_error}"
                                )

                        candidates = list(temporary_dir.rglob("density.mhd"))
                        if not candidates:
                            candidates = list(temporary_dir.rglob("energy.mhd"))
                        if not candidates:
                            print(
                                f"[{gene}] Dataset {dataset_id} contained no "
                                "density/energy MHD."
                            )
                            continue

                        print(f"[{gene}] Converting MHD to NRRD...")
                        image = sitk.ReadImage(str(candidates[0]))
                        temporary_output = output_nrrd.with_name(
                            f"{output_nrrd.stem}.tmp.nrrd"
                        )
                        sitk.WriteImage(image, str(temporary_output), useCompression=True)
                        temporary_output.replace(output_nrrd)
                        write_json_atomic(
                            output_nrrd.with_suffix(".manifest.json"),
                            artifact_manifest(
                                artifact_type="allen_gene_expression_volume",
                                gene=gene,
                                allen_dataset_id=int(dataset_id),
                                source_url=download_url,
                                output=output_nrrd.name,
                                size=list(image.GetSize()),
                                spacing_um=list(image.GetSpacing()),
                                origin_um=list(image.GetOrigin()),
                                direction=list(image.GetDirection()),
                            ),
                        )
                        print(f"[SUCCESS] Saved {gene} to {output_nrrd.name}")
                        success_for_gene = True
                        break

                if not success_for_gene:
                    print(f"[ERROR] {gene}: Exhausted all available datasets! No valid grid downloaded.")
                    all_succeeded = False

            else:
                print(f"[WARNING] No datasets found for {gene}.")
                all_succeeded = False

        except Exception as e:
            print(f"[ERROR] Failed to fetch {gene}:\n{traceback.format_exc()}")
            all_succeeded = False
    return all_succeeded


def main() -> int:
    ensure_runtime_directories()
    return 0 if fetch_all_genes() else 1


if __name__ == "__main__":
    raise SystemExit(main())
