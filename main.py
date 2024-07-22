import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.simpledialog import askstring
from pathlib import Path
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
import geopandas as gpd
import rasterio
import io
import webbrowser

from detectree2.preprocessing.tiling import tile_data
from detectree2.models.outputs import project_to_geojson, stitch_crowns, clean_crowns
from detectree2.models.predict import predict_on_data
from detectree2.models.train import setup_cfg
from detectron2.engine import DefaultPredictor

# Default settings
settings = {
    "main": {
        "site_path": "/home/tobias/detectree2/",
        "tiles_path": "/home/tobias/detectree2/tilespred/"
    },
    "tiling": {
        "buffer": 30,
        "tile_width": 40,
        "tile_height": 40
    },
    "crown": {
        "confidence": 0.6
    }
}

def convert_to_tif(image_path):
    """Convert an image to TIFF format."""
    img = Image.open(image_path)
    img = img.convert("RGB")
    tif_path = image_path.with_suffix('.tif')
    img.save(tif_path, format='TIFF')
    return tif_path

def load_model(model_path):
    """Load the model configuration."""
    cfg = setup_cfg(update_model=str(model_path))
    cfg.MODEL.DEVICE = "cpu"
    return cfg

def evaluate_image(image_path, model_path, evaluated_image_label):
    """Evaluate an image using the provided model."""
    if image_path.suffix.lower() not in ['.tif', '.png', '.jpg', '.jpeg']:
        print("Unsupported file format. Please provide a .tif, .png, or .jpg image.")
        return

    if image_path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
        image_path = convert_to_tif(image_path)

    data = rasterio.open(image_path)

    site_path = settings['main']['site_path']
    tiles_path = settings['main']['tiles_path']

    buffer = settings['tiling']['buffer']
    tile_width = settings['tiling']['tile_width']
    tile_height = settings['tiling']['tile_height']
    
    tile_data(data, tiles_path, buffer, tile_width, tile_height, dtype_bool=True)

    cfg = load_model(model_path)
    predict_on_data(tiles_path, predictor=DefaultPredictor(cfg))
    project_to_geojson(tiles_path, tiles_path + "predictions/", tiles_path + "predictions_geo/")

    crowns = stitch_crowns(tiles_path + "predictions_geo/", 1)
    clean = clean_crowns(crowns, 0.6, confidence=0)
    clean = clean[clean["Confidence_score"] > settings['crown']['confidence']]
    clean = clean.set_geometry(clean.simplify(0.3))
    clean.to_file(site_path + "/crowns_out.gpkg")

    predictions_img = overlay_image_with_gpkg(image_path, site_path + "/crowns_out.gpkg")

    evaluated_image_label.config(image=predictions_img)
    evaluated_image_label.image = predictions_img
    messagebox.showinfo("Evaluation Result", "Evaluation complete")

def plot_base_image(image_path):
    """Plot the base image."""
    base_image = Image.open(image_path)
    plt.imshow(base_image)
    return base_image.size

def plot_geopackage(gpkg_path, image_size):
    """Plot the GeoPackage geometries over the image."""
    gdf = gpd.read_file(gpkg_path)
    gdf = gdf.to_crs(epsg=4326)

    bounds = gdf.total_bounds
    x_scale = image_size[0] / (bounds[2] - bounds[0])
    y_scale = image_size[1] / (bounds[3] - bounds[1])

    for geometry in gdf.geometry:
        x, y = geometry.exterior.xy
        x = [(xi - bounds[0]) * x_scale for xi in x]
        y = [(bounds[3] - yi) * y_scale for yi in y]
        plt.plot(x, y, color='red')

def overlay_image_with_gpkg(image_path, gpkg_path):
    """Overlay the base image with GeoPackage geometries."""
    plt.figure(figsize=(10, 10))
    image_size = plot_base_image(image_path)
    plot_geopackage(gpkg_path, image_size)
    plt.axis('off')

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()

    img = Image.open(buf)
    return ImageTk.PhotoImage(img)

def select_image(image_label, image_path_var):
    """Handle image selection dialog."""
    file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.tif *.png *.jpg *.jpeg")])
    if file_path:
        image_path_var.set(file_path)
        image = Image.open(file_path)
        image.thumbnail((250, 250))
        image = ImageTk.PhotoImage(image)
        image_label.config(image=image)
        image_label.image = image

def open_model_download_page():
    """Open the models download page in a web browser."""
    webbrowser.open("https://zenodo.org/records/10522461")

def refresh_model_list(model_path_var, model_files_frame):
    """Refresh the model files list."""
    current_directory = Path(__file__).parent
    model_files = list(current_directory.glob("*.pth"))
    
    if not model_files:
        messagebox.showerror("Error", "No model files found in the current directory.")
        return
    
    # Clear existing radio buttons
    for widget in model_files_frame.winfo_children():
        widget.destroy()
    
    # Add new radio buttons
    for model_file in model_files:
        tk.Radiobutton(model_files_frame, text=model_file.name, variable=model_path_var, value=str(model_file)).pack(anchor=tk.W)

def open_settings():
    """Open the settings window."""
    settings_window = tk.Toplevel()
    settings_window.title("Settings")
    settings_window.geometry("400x600")

    # Main settings
    tk.Label(settings_window, text="Main Settings", font=('Helvetica', 12, 'bold')).pack(anchor=tk.W, pady=5)
    tk.Label(settings_window, text="Settings for the main paths.").pack(anchor=tk.W, pady=5)

    for key, value in settings['main'].items():
        tk.Label(settings_window, text=f"{key} (default: {value})").pack(anchor=tk.W)
        entry = tk.Entry(settings_window)
        entry.insert(0, value)
        entry.pack(anchor=tk.W, padx=20)
        entry.bind("<FocusOut>", lambda e, k=key: update_setting('main', k, entry.get()))

    # Tiling settings
    tk.Label(settings_window, text="Tiling Settings", font=('Helvetica', 12, 'bold')).pack(anchor=tk.W, pady=5)
    tk.Label(settings_window, text="Settings for tiling the image.").pack(anchor=tk.W, pady=5)

    for key, value in settings['tiling'].items():
        tk.Label(settings_window, text=f"{key} (default: {value})").pack(anchor=tk.W)
        entry = tk.Entry(settings_window)
        entry.insert(0, value)
        entry.pack(anchor=tk.W, padx=20)
        entry.bind("<FocusOut>", lambda e, k=key: update_setting('tiling', k, entry.get()))

    # Crown settings
    tk.Label(settings_window, text="Crown Settings", font=('Helvetica', 12, 'bold')).pack(anchor=tk.W, pady=5)
    tk.Label(settings_window, text="Settings for crown detection.").pack(anchor=tk.W, pady=5)

    for key, value in settings['crown'].items():
        tk.Label(settings_window, text=f"{key} (default: {value})").pack(anchor=tk.W)
        entry = tk.Entry(settings_window)
        entry.insert(0, value)
        entry.pack(anchor=tk.W, padx=20)
        entry.bind("<FocusOut>", lambda e, k=key: update_setting('crown', k, entry.get()))

def update_setting(section, key, value):
    """Update a setting in the settings dictionary."""
    settings[section][key] = type(settings[section][key])(value)  # Convert to appropriate type

def create_gui():
    """Create the GUI for image evaluation."""
    root = tk.Tk()
    root.title("Image Evaluation")

    current_directory = Path(__file__).parent
    model_files = list(current_directory.glob("*.pth"))

    model_path_var = tk.StringVar(value=str(model_files[0]) if model_files else "")

    # Model selection frame
    model_files_frame = tk.Frame(root)
    model_files_frame.pack(anchor=tk.W, padx=10, pady=10)
    tk.Label(model_files_frame, text="Select Model:").pack(anchor=tk.W)

    for model_file in model_files:
        tk.Radiobutton(model_files_frame, text=model_file.name, variable=model_path_var, value=str(model_file)).pack(anchor=tk.W)

    if not model_files:
        tk.Button(model_files_frame, text="Download Models", command=open_model_download_page).pack(anchor=tk.W)
        tk.Button(model_files_frame, text="Refresh", command=lambda: refresh_model_list(model_path_var, model_files_frame)).pack(anchor=tk.W)

    # Image selection and display
    image_path_var = tk.StringVar()

    left_frame = tk.Frame(root)
    left_frame.pack(side=tk.LEFT, padx=10, pady=10)

    tk.Label(left_frame, text="Original Image").pack(anchor=tk.W)
    original_image_label = tk.Label(left_frame)
    original_image_label.pack(anchor=tk.W)

    tk.Label(left_frame, text="Selected Image:").pack(anchor=tk.W)
    tk.Entry(left_frame, textvariable=image_path_var, width=50).pack(anchor=tk.W)
    tk.Button(left_frame, text="Select Image", command=lambda: select_image(original_image_label, image_path_var)).pack(anchor=tk.W)

    # Evaluated image display
    right_frame = tk.Frame(root)
    right_frame.pack(side=tk.RIGHT, padx=10, pady=10)

    tk.Label(right_frame, text="Evaluated Image").pack(anchor=tk.W)
    evaluated_image_label = tk.Label(right_frame)
    evaluated_image_label.pack(anchor=tk.W)

    def on_evaluate():
        if not image_path_var.get():
            messagebox.showerror("Error", "Please select an image file.")
            return

        evaluate_image(Path(image_path_var.get()), Path(model_path_var.get()), evaluated_image_label)

    tk.Button(root, text="Evaluate Image!", command=on_evaluate).pack(anchor=tk.SE, pady=10, padx=10)
    
    # Settings button
    tk.Button(root, text="Settings", command=open_settings).pack(anchor=tk.S, pady=10)

    root.mainloop()

if __name__ == "__main__":
    create_gui()
