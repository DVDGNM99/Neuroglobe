import sys
from pathlib import Path

# Ensure src is in path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from brainglobe_atlasapi import BrainGlobeAtlas
from brainrender import Scene, actors

def test_split_rendering():
    """
    Prototype to verify we can render the Left and Right hemispheres 
    of the same region with different colors.
    """
    print("Initializing Scene...")
    scene = Scene(atlas_name="allen_mouse_25um", title="Hemisphere Split Test")

    # Region to test: Secondary Motor Area (MOs)
    region = "MOs"
    
    print(f"Adding {region} (Left - RED)...")
    # 1. Left Hemisphere Actor
    # We add the whole region, then clip it.
    # CCF Midline is roughly 5700 um (11400 / 2)
    # Plane: origin at (5700, 0, 0), normal (1, 0, 0) keeps one side?
    # brainrender's cut_with_plane keeps the part *behind* the normal? or in front?
    # Let's try.
    
    actor_left = scene.add_brain_region(region, alpha=1.0, color="red")
    
    # Cut logic:
    # We want X < 5700 (Left).
    # Plane at 5700. Normal pointing +X (1,0,0) -> Removes X > 5700 ??
    # vedo.cutWithPlane(origin, normal) cuts what is on the 'positive' side of the normal?
    
    midline_x = 5700 
    # Center of the brain is roughly: 5700, 4000, 5600
    
    # Clip to keep Left
    # If normal is (1,0,0), it cuts everything "above" the plane?
    actor_left.cut_with_plane(origin=(midline_x, 0, 0), normal=(1, 0, 0))
    actor_left.name = f"{region}_Left"

    print(f"Adding {region} (Right - BLUE)...")
    # 2. Right Hemisphere Actor
    actor_right = scene.add_brain_region(region, alpha=1.0, color="blue")
    
    # Clip to keep Right
    # Normal (-1, 0, 0) should cut the other side
    actor_right.cut_with_plane(origin=(midline_x, 0, 0), normal=(-1, 0, 0))
    actor_right.name = f"{region}_Right"

    print("Rendering... (Close window to finish test)")
    scene.render(interactive=True)

if __name__ == "__main__":
    test_split_rendering()
