# detectree2_wrapper.py
from pathlib import Path
from PIL import Image
import matplotlib.pyplot as plt
import geopandas as gpd
import rasterio
import io
import os

from detectree2.preprocessing.tiling import tile_data
from detectree2.models.outputs import project_to_geojson, stitch_crowns, clean_crowns
from detectree2.models.predict import predict_on_data
from detectree2.models.train import setup_cfg
from detectron2.engine import DefaultPredictor

class Detectree2:
    def __init__(self, settings):
        self.settings = settings
        print(settings)

    def convert_to_tif(self, image_path):
        """Convert an image to TIFF format."""
        img = Image.open(image_path)
        img = img.convert("RGB")
        tif_path = image_path.with_suffix('.tif')
        img.save(tif_path, format='TIFF')
        return tif_path

    def load_model(self, model_path):
        """Load the model configuration."""
        cfg = setup_cfg(update_model=str(model_path))
        cfg.MODEL.DEVICE = "cpu"
        return cfg

    def evaluate_image(self, image_path, model_path):
        """Evaluate an image using the provided model."""
        if image_path.suffix.lower() not in ['.tif', '.tiff', '.png', '.jpg', '.jpeg']:
            raise ValueError("Unsupported file format. Please provide a .tif, .png, or .jpg image.")

        if image_path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
            image_path = self.convert_to_tif(image_path)

        data = rasterio.open(image_path)

        site_path = self.settings['main']['site_path']
        tiles_path = self.settings['main']['tiles_path']

        buffer = self.settings['tiling']['buffer']
        tile_width = self.settings['tiling']['tile_width']
        tile_height = self.settings['tiling']['tile_height']
        
        tile_data(data, tiles_path, buffer, tile_width, tile_height, dtype_bool=True)

        cfg = self.load_model(model_path)
        
        predict_on_data(tiles_path, predictor=DefaultPredictor(cfg))
        project_to_geojson(tiles_path, tiles_path + "predictions/", tiles_path + "predictions_geo/")

        crowns = stitch_crowns(tiles_path + "predictions_geo/", 1)
        clean = clean_crowns(crowns, 0.6, confidence=0)
        clean = clean[clean["Confidence_score"] > self.settings['crown']['confidence']]
        clean = clean.set_geometry(clean.simplify(0.3))
        clean.to_file(site_path + "/crowns_out.gpkg")

        predictions_img = self.overlay_image_with_gpkg(image_path, site_path + "/crowns_out.gpkg")
        return predictions_img

    def plot_base_image(self, image_path):
        """Plot the base image."""
        base_image = Image.open(image_path)
        plt.imshow(base_image)
        return base_image.size

    def plot_geopackage(self, gpkg_path, image_size):
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

    def overlay_image_with_gpkg(self, image_path, gpkg_path):
        """Overlay the base image with GeoPackage geometries."""
        plt.figure(figsize=(10, 10))
        image_size = self.plot_base_image(image_path)
        self.plot_geopackage(gpkg_path, image_size)
        plt.axis('off')
        plt.gca().set_axis_off()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        plt.close()

        img = Image.open(buf)
        
        # Limit the width to a maximum of 2500 pixels while maintaining the aspect ratio
        max_width = 2500
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = int((float(img.height) * float(ratio)))
            img = img.resize((max_width, new_height), Image.LANCZOS)

        return img
