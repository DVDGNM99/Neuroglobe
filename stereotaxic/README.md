# Neuroglobe Stereotaxic

Viewer sperimentale per mesh BrainGlobe, piano coronal AP e coordinate rispetto
a costanti Bregma approssimate.

```powershell
python -m neuroglobe.stereotaxic.gui
```

Protocollo:

```text
stdin:  SLICE|{AP_MICRONS}
stdout: SLICE_ACK|{AP_MICRONS}
stdout: COORD_APPROX|{AP_MM}|{ML_MM}|{DV_MM}
```

Il listener stdin accoda gli aggiornamenti; il piano VTK viene modificato e
ridisegnato esclusivamente sul render thread. stdout/stderr sono unificati e
il processo figlio viene terminato quando la GUI si chiude.

Le coordinate sono esplicitamente “approximate/unvalidated”. Le costanti
`BREGMA_AP_UM=5375`, `BREGMA_ML_UM=5700` e `BREGMA_DV_UM=200` non
costituiscono una trasformazione stereotaxic validata.
