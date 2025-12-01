import sys
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.colorbar as cbar
import argparse

def show_legend(vmin, vmax, colormap="viridis"):
    # Setup figure for the legend
    fig = plt.figure(figsize=(4, 6))
    ax = fig.add_axes([0.3, 0.1, 0.2, 0.8]) # [left, bottom, width, height]
    
    # Create normalization and colormap
    # Scale to percentages (0-1 -> 0-100)
    norm = mcolors.Normalize(vmin=vmin*100, vmax=vmax*100)
    cmap = plt.get_cmap(colormap)
    
    # Create colorbar
    cb = cbar.ColorbarBase(ax, cmap=cmap, norm=norm, orientation='vertical')
    cb.set_label('Projection Density (Volume %)')
    
    fig.canvas.manager.set_window_title('Neuroglobe Legend')
    
    print(f"Showing legend: {vmin} - {vmax}")
    plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--min", type=float, required=True)
    parser.add_argument("--max", type=float, required=True)
    args = parser.parse_args()
    
    show_legend(args.min, args.max)
