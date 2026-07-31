# Testing Workflow

Dalla root:

```powershell
python -m pytest --collect-only -q
python -m pytest -q
```

Nell’ambiente `brainglobe_render`, i plugin pytest installati da
Napari/Qt possono rallentare o bloccare l’autoload. Per il percorso unit:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
python -m pytest -q
```

Stato verificato il 2026-07-31:

```text
33 passed, 2 skipped
```

La suite esercita direttamente:

- convenzione AP/DV/ML e lateralità da `injection_z`;
- aggregazione Left/Right/Ipsi/Contra e trattamento unknown;
- preservazione del NRRD Allen e ordine array SimpleITK;
- errori di shape/target del filtro;
- contratto tipizzato e validazione CSV;
- split `Both` sul piano ML/Z;
- config validation, subprocess supervision e package boundaries.

Il test BrainRender interattivo è marcato `gui`/`integration` e saltato nel
percorso headless. Restano da aggiungere test scientifici end-to-end con
phantom asimmetrico, landmark noti, Dice/Hausdorff e rendering offscreen.
