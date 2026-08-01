# Neuroglobe Walkthrough

Eseguire i comandi dalla root del repository. I moduli Python canonici sono
sotto `neuroglobe/`; `projections/`, `genetics/` e `stereotaxic/` conservano
configurazioni, dati, GUI e documentazione.

## 1. Configurare projections

Modificare `projections/configs/mining_config.yaml`:

- `experiment.seed_acronym`: seed Allen;
- `experiment.target_regex`: pattern degli acronimi inclusi;
- `processing.metric`: metrica Allen;
- `processing.aggregation_mode`: `mean`, `median` o `max`;
- `quality_control.min_injection_volume`: soglia esperimenti;
- `quality_control.threshold_lower`: valori aggregati sotto soglia azzerati;
- `selection.custom_targets`: target del CSV/volume filtrato.

La configurazione viene validata e i target duplicati sono rimossi mantenendo
l’ordine.

## 2. Eseguire il miner

Con l’ambiente AllenSDK:

```powershell
python -m neuroglobe.projections.miner.fetch
python -m neuroglobe.projections.miner.extract_tracts
python -m neuroglobe.projections.miner.aggregate
python -m neuroglobe.projections.miner.filter_csv
```

`aggregate`:

- usa `injection_z` come coordinata ML;
- esclude dal calcolo ipsi/contra coordinate mancanti o sul midline;
- calcola `value_mean` dalla media dei risultati Left/Right, senza mescolare
  Allen hemisphere ID 3;
- salva un solo primary seed;
- produce un manifest accanto al CSV.

L’estrattore copia il NRRD Allen originale quando presente nella cache. Non
ricostruisce più spacing/orientamento con euristiche.

## 3. Viewer projections

```powershell
python -m neuroglobe.projections.viewer.main
```

Caricare un CSV, scegliere le regioni e il data mode. `Both` divide ogni mesh
sull’asse ML/Z. “Filter Raw Volume” crea:

```text
{experiment_id}_{metric}_{config_hash}.vtk
{experiment_id}_{metric}_{config_hash}.manifest.json
```

Il viewer riutilizza la mesh solo nella sessione/experiment ID compatibile.
Shape o spacing incompatibili con l’atlas causano un errore esplicito.

## 4. Genetics

```powershell
python genetics/GUI_caller/genetics_gui.py
```

La pipeline:

1. scarica via HTTPS ogni dataset in una directory temporanea isolata;
2. valida i path dello ZIP;
3. registra l’Allen dataset ID nel manifest del volume;
4. ricampiona la mask CCF nello spazio fisico del volume con interpolazione
   nearest-neighbor;
5. conserva spacing, origin e direction SimpleITK.

Il renderer usa direttamente la geometria NRRD, senza `permute_axes`, scaling
automatico o rotazioni correttive.

## 5. Scena integrata genetics + projections

Il comando integrato accetta almeno un NRRD projection density e un NRRD di
espressione genica. Creare la specifica dalla root del repository, in modo che
i path sorgente rimangano relativi e portabili:

```powershell
python -m neuroglobe.integration.cli compose `
  --output integrated_scene.json `
  --projection experiment-180719293=projections/data/raw/experiment_180719293/projection_density_25.nrrd `
  --gene Cux2=genetics/data/processed/Cux2_filtered.nrrd `
  --region PL --region CP

python -m neuroglobe.integration.cli validate integrated_scene.json
python -m neuroglobe.integration.cli render integrated_scene.json
```

`compose` legge soltanto gli header NRRD, registra geometria e SHA-256 e
rifiuta volumi fuori dal frame fisico Allen. Risoluzioni diverse sono ammesse:
per esempio projection density a 25 um ed expression grid a 200 um possono
condividere lo stesso frame. Non vengono applicate rotazioni, permutazioni,
scale o traslazioni runtime. Dopo il rendering viene scritto un manifest di run
immutabile accanto alla specifica.

## 6. Stereotaxic

```powershell
python -m neuroglobe.stereotaxic.gui
```

Il protocollo è:

```text
stdin:  SLICE|{AP_MICRONS}
stdout: SLICE_ACK|{AP_MICRONS}
stdout: COORD_APPROX|{AP_MM}|{ML_MM}|{DV_MM}
```

Gli aggiornamenti VTK vengono applicati dal render thread tramite timer. Le
coordinate sono mostrate a una cifra decimale e marcate “unvalidated”.

## 7. Verifica

```powershell
python -m pytest -q
```

I test interattivi BrainRender sono marcati `gui`/`integration` e saltati nel
percorso headless. Il test Allen reale si abilita soltanto quando l'atlas e'
gia' presente nella cache locale:

```powershell
$env:NEUROGLOBE_RUN_ATLAS_TESTS = "1"
python -m pytest -q tests/test_real_atlas.py
```
