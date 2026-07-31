# Neuroglobe Genetics

Prototipo per scaricare griglie Allen di espressione genica, limitarle a
regioni CCF e renderizzarle come legosurface.

```text
configs/manifest.json
  -> neuroglobe.genetics.miner.fetch_genes
  -> data/raw/{GENE}_density.nrrd + manifest
  -> neuroglobe.genetics.miner.filter_volume
  -> data/processed/{GENE}_filtered.nrrd
  -> neuroglobe.genetics.viewer.controller
```

Avvio:

```powershell
python genetics/GUI_caller/genetics_gui.py
```

Il download usa HTTPS, streaming, timeout, estrazione ZIP validata e directory
temporanee per dataset. Il filtro converte la mask BrainGlobe AP/DV/ML in un
volume SimpleITK e la ricampiona sulla geometria fisica del gene con
nearest-neighbor. Il renderer non permuta né riscala gli assi.

La soglia visuale resta il 90° percentile non-zero per gene: è un confronto
relativo, non una misura quantitativa validata tra geni. Servono ancora
landmark gold-standard per certificare l’allineamento end-to-end.
