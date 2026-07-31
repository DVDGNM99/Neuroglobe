# Neuroglobe Stereotaxic

Viewer sperimentale per mesh BrainGlobe, piano coronal AP e coordinate rispetto
al profilo versionato `elife-67291-ccfv3-bregma/v1`.

```powershell
python -m neuroglobe.stereotaxic.gui
```

Protocollo:

```text
stdin:  SLICE|{AP_MICRONS}
stdout: SLICE_ACK|{AP_MICRONS}
stdout: COORD_ESTIMATE|{PROFILE_ID}|{AP_MM}|{ML_MM}|{DV_MM}
```

Il listener stdin accoda gli aggiornamenti; il piano VTK viene modificato e
ridisegnato esclusivamente sul render thread. stdout/stderr sono unificati e
il processo figlio viene terminato quando la GUI si chiude.

La conversione pubblicata usa Bregma CCF AP/DV/ML `(5400, 0, 5700)` um ed è
verificata con landmark e round-trip automatici. CCFv3 non ha però un Bregma
cranico intrinseco: il profilo è una stima di letteratura per visualizzazione,
non una calibrazione validata per targeting chirurgico individuale.

Riferimenti:

- conversione CCF/Bregma: DOI `10.7554/eLife.67291`;
- definizione CCFv3 e limite del rapporto con Bregma: DOI
  `10.1016/j.cell.2020.04.007`.
