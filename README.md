# Neuroglobe

Neuroglobe 5.0 raccoglie tre strumenti di ricerca basati su Allen CCF e
BrainGlobe:

- `projections`: mining Allen Mouse Connectivity, aggregazione e viewer 3D;
- `genetics`: download, mascheratura fisica e rendering di expression grids;
- `stereotaxic`: viewer sperimentale con piano AP e coordinate Bregma
  approssimate.

La review originale è in [FULL_CODE_REVIEW.md](FULL_CODE_REVIEW.md). Le
correzioni implementate dopo la review non rendono automaticamente validati i
risultati scientifici storici: CSV, NRRD, VTK e scene precedenti devono essere
rigenerati, e alignment/coordinate richiedono ancora un gold standard esterno.

## Correzioni implementate

- package unico `neuroglobe` 5.0.0, senza namespace top-level `src` né
  manipolazioni di `sys.path`;
- convenzione condivisa `x=AP`, `y=DV`, `z=ML`, unità in micrometri;
- lateralità calcolata da Allen `injection_z`, con midline/missing espliciti;
- split `Both` sul piano medio-sagittale ML/Z derivato dalla geometria atlas;
- NRRD projection density Allen conservato con header originale;
- rimozione di rotazioni, scaling e permutazioni euristiche nei renderer;
- maschere genetics ricampionate nello spazio fisico con nearest-neighbor;
- config validata, QC minimo applicato e target deduplicati;
- metriche Allen density, energy e projection volume selezionabili dal Miner;
- projection energy 3D scaricata come NRRD tramite l'API grid Allen supportata;
- mesh filtrate legate a experiment/config hash con sidecar di provenance;
- download genetics HTTPS, streaming, timeout, estrazione ZIP sicura e
  directory temporanee isolate;
- subprocess GUI con stream unificati, timeout, cancellazione e progress;
- operazioni di masking volumetrico chunked con memoria di lavoro limitata;
- validazione con phantom asimmetrico, metriche fisiche e landmark Allen reali
  opzionali dalla cache locale;
- scene integrate genetics/projections con schema, checksum, provenance e
  validazione preventiva della geometria AP/DV/ML;
- protocollo average-volume vincolato a registrazione/QC, con media, varianza
  campionaria e CI 95% Student-t voxel-wise su array memory-mapped, esportabili
  in NRRD fisico verificato;
- CI Windows/Linux e test headless isolati dalle dipendenze GUI.

## Installazione

Dalla root:

```powershell
# Miner projections
conda activate allensdk
python -m pip install -e ".[miner,desktop]"

# Viewer projections e stereotaxic
conda activate brainglobe_render
python -m pip install -e ".[viewer,desktop]"
```

Genetics usa AllenSDK, SimpleITK e BrainGlobe; predisporre un ambiente che
includa gli extra `miner`, `viewer` e `desktop`.

## Avvio

```powershell
# Launcher projections
python projections/GUI_caller/launcher.py

# Moduli canonici
python -m neuroglobe.projections.miner.fetch
python -m neuroglobe.projections.miner.extract_tracts
python -m neuroglobe.projections.miner.aggregate
python -m neuroglobe.projections.miner.filter_csv
python -m neuroglobe.projections.miner.average_volume_cli --help
python -m neuroglobe.projections.viewer.main

# Genetics
python genetics/GUI_caller/genetics_gui.py

# Scena integrata genetics + projections
python -m neuroglobe.integration.cli --help

# Stereotaxic
python -m neuroglobe.stereotaxic.gui
```

Dopo l’installazione sono disponibili anche i console script dichiarati in
`pyproject.toml`, tra cui `neuroglobe-fetch`, `neuroglobe-aggregate`,
`neuroglobe-average-volume`, `neuroglobe-viewer` e
`neuroglobe-integrated-viewer`.

Nel pannello Genetics, il pulsante **Projection + Genes** usa i geni e le
regioni selezionati, chiede un projection-density NRRD e avvia lo stesso flusso
integrato con validazione e job cancellabile.

## Test e build

```powershell
python -m compileall -q neuroglobe projections/GUI_caller genetics/GUI_caller
python -m pytest -q
python -m pip wheel . --no-deps --wheel-dir .tmp-wheel
```

Stato verificato il 2026-08-01: 86 test passati, 3 skip intenzionali; wheel
`neuroglobe-5.0.0-py3-none-any.whl` costruita correttamente.

## Limiti scientifici residui

- gli artefatti generati prima di questa migrazione non hanno geometria o
  lateralità affidabili;
- manca ancora un gold-standard esterno indipendente end-to-end per le mesh;
- il viewer standard usa ancora un volume rappresentativo single-animal; il
  protocollo average-volume richiede volumi registrati esternamente e non
  interpreta come registrati i vecchi NRRD;
- le soglie di isosurface e percentile genetics non sono validate
  biologicamente;
- le coordinate stereotaxic sono dichiaratamente approssimate e non sono una
  trasformazione stereotaxic validata;
- BrainRender può dipendere dai permessi della cache BrainGlobe dell’utente.

I dettagli operativi sono in [walkthrough.md](walkthrough.md); finding,
motivazioni e roadmap completa restano in
[FULL_CODE_REVIEW.md](FULL_CODE_REVIEW.md).
