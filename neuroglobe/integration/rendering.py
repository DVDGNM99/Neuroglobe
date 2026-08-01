"""Lazy BrainRender renderer for validated integrated scene specifications."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from neuroglobe.integration.model import IntegratedSceneSpec, LayerKind, SceneLayer


@dataclass
class IntegratedRenderResult:
    success: bool
    regions_rendered: int = 0
    projections_rendered: int = 0
    genes_rendered: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class IntegratedRenderEngine:
    """Render projection and expression volumes in one physical CCF frame."""

    def __init__(self, spec: IntegratedSceneSpec):
        self.spec = spec

    def render(
        self,
        *,
        interactive: bool = True,
        show_legend: bool = True,
        validate_sources: bool = True,
    ) -> IntegratedRenderResult:
        if validate_sources:
            self.spec.validate_sources()

        # Optional graphics libraries remain entirely outside import/validation
        # paths, which keeps compose and validate usable in miner-only setups.
        from brainrender import Scene
        from vedo import LegendBox, Volume

        scene = Scene(atlas_name=self.spec.atlas_name, title="Integrated Neuroglobe Scene")
        result = IntegratedRenderResult(success=False)
        legend_actors = []

        try:
            root = scene.add_brain_region("root", alpha=0.04, color="grey")
            if root is not None:
                root.wireframe()
        except Exception as error:
            result.warnings.append(f"Root region: {error}")

        for layer in self.spec.layers:
            try:
                actor = self._render_layer(scene, Volume, layer)
                if actor is None:
                    result.warnings.append(f"{layer.identifier}: empty layer")
                    continue
                legend_actors.append(actor)
                if layer.kind is LayerKind.REGION:
                    result.regions_rendered += 1
                elif layer.kind is LayerKind.PROJECTION_VOLUME:
                    result.projections_rendered += 1
                else:
                    result.genes_rendered += 1
            except Exception as error:
                result.errors.append(f"{layer.identifier}: {error}")

        if show_legend and legend_actors:
            legend = LegendBox(entries=legend_actors, width=0.22, height=None)
            scene.add(legend)

        result.success = (
            not result.errors
            and result.projections_rendered > 0
            and result.genes_rendered > 0
        )
        if result.success:
            scene.render(interactive=interactive, zoom=1.2)
        return result

    @staticmethod
    def _render_layer(scene, volume_class, layer: SceneLayer):
        style = layer.style
        if layer.kind is LayerKind.REGION:
            actor = scene.add_brain_region(
                layer.acronym,
                alpha=style.alpha,
                color=style.color or "lightgrey",
            )
            if actor is not None:
                actor.name = layer.label
                if style.wireframe:
                    actor.wireframe()
            return actor

        volume = volume_class(str(layer.source))
        if layer.kind is LayerKind.PROJECTION_VOLUME:
            scalar_min, scalar_max = volume.scalar_range()
            if not np.isfinite(scalar_max) or scalar_max <= 0:
                return None
            threshold = scalar_max * style.projection_threshold_fraction
            actor = volume.isosurface(value=threshold)
            if style.color:
                actor.c(style.color)
            else:
                actor.cmap("viridis", vmin=max(scalar_min, threshold), vmax=scalar_max)
        elif layer.kind is LayerKind.GENE_EXPRESSION:
            values = np.asarray(volume.tonumpy())
            finite_positive = values[np.isfinite(values) & (values > 0)]
            if finite_positive.size == 0:
                return None
            threshold = float(np.percentile(finite_positive, style.gene_percentile))
            actor = volume.legosurface(vmin=threshold)
            actor.c(style.color or "red")
        else:  # pragma: no cover - enum construction makes this unreachable
            raise ValueError(f"Unsupported integrated layer kind: {layer.kind}")

        actor.alpha(style.alpha)
        actor.name = layer.label
        scene.add(actor)
        return actor
