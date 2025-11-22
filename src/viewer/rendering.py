from brainglobe_atlasapi import BrainGlobeAtlas
from brainrender import Scene

class RenderEngine:
    def __init__(self, atlas_name="allen_mouse_25um"):
        print(f"Initializing Atlas: {atlas_name}...")
        self.atlas = BrainGlobeAtlas(atlas_name)
        self.atlas_name = atlas_name

    def validate_regions(self, regions: list) -> tuple:
        """
        Checks if regions exist in the atlas hierarchy.
        Returns (valid_list, invalid_list)
        """
        valid = []
        invalid = []
        for r in regions:
            try:
                # Check if acronym exists in ontology
                _ = self.atlas.structure_from_acronym(r)
                valid.append(r)
            except Exception:
                invalid.append(r)
        return valid, invalid

    def render_scene(self, region_config: list, alpha=0.5, background="black"):
        """
        region_config: list of dict {'acronym': str, 'color': str (hex)}
        """
        scene = Scene(atlas_name=self.atlas_name, title="Neuroglobe Viewer")
        # Setting background requires internal access or settings change usually, 
        # relying on defaults for now to keep it safe.

        print(f"Building scene with {len(region_config)} regions...")
        
        missing_meshes = []

        for item in region_config:
            acr = item['acronym']
            col = item['color']
            
            try:
                # Try to add the region. 
                # Brainrender raises Error if mesh is missing.
                scene.add_brain_region(acr, alpha=alpha, color=col)
            except Exception as e:
                print(f"Warning: Could not render mesh for '{acr}'. Reason: {e}")
                missing_meshes.append(acr)

        scene.render()
        return missing_meshes