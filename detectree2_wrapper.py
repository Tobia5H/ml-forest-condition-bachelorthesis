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

from logger_config import LoggerConfig

class Detectree2:
    def __init__(self, settings):
        """
        Initializes the Detectree2 class with the provided settings.

        Args:
            settings (dict): A dictionary containing settings for tiling, crown confidence, and file paths.
        """
        self.logger = LoggerConfig.get_logger(self.__class__.__name__)
        self.settings = settings
        self.logger.info(f"Detectree2 initialized with settings: {settings}")

    def convert_to_tif(self, image_path):
        """
        Convert an image to TIFF format.

        Args:
            image_path (Path): The path to the image to be converted.

        Returns:
            Path: The path to the converted TIFF image.
        """
        self.logger.info(f"Converting image {image_path} to TIFF format.")
        img = Image.open(image_path)
        img = img.convert("RGB")
        tif_path = image_path.with_suffix('.tif')
        img.save(tif_path, format='TIFF')
        self.logger.info(f"Image saved as {tif_path}")
        return tif_path

    def load_model(self, model_path):
        """
        Load the model configuration.

        Args:
            model_path (Path): The path to the model configuration file.

        Returns:
            cfg: The loaded model configuration.
        """
        self.logger.info(f"Loading model from {model_path}")
        cfg = setup_cfg(update_model=str(model_path))
        cfg.MODEL.DEVICE = "cpu"
        self.logger.info("Model configuration loaded.")
        return cfg

    def evaluate_image(self, image_path, model_path):
        """
        Evaluate an image using the provided model.

        Args:
            image_path (Path): The path to the image to be evaluated.
            model_path (Path): The path to the model configuration.

        Returns:
            Image: The resulting image with overlaid predictions.

        Raises:
            ValueError: If the image file format is unsupported.
        """
        self.logger.info(f"Evaluating image {image_path} using model {model_path}")
        if image_path.suffix.lower() not in ['.tif', '.tiff', '.png', '.jpg', '.jpeg']:
            self.logger.error("Unsupported file format. Please provide a .tif, .png, or .jpg image.")
            raise ValueError("Unsupported file format. Please provide a .tif, .png, or .jpg image.")

        data = rasterio.open(image_path)

        site_path = self.settings['main']['site_path']
        tiles_path = self.settings['main']['tiles_path']

        buffer = int(self.settings['tiling']['buffer'])
        tile_width = int(self.settings['tiling']['tile_width'])
        tile_height = int(self.settings['tiling']['tile_height'])
        
        self.logger.info("Tiling the data.")
        tile_data(data, tiles_path, buffer, tile_width, tile_height, dtype_bool=True)

        cfg = self.load_model(model_path)
        
        self.logger.info("Predicting on the tiled data.")
        predict_on_data(tiles_path, predictor=DefaultPredictor(cfg))
        project_to_geojson(tiles_path, tiles_path + "predictions/", tiles_path + "predictions_geo/")

        self.logger.info("Stitching and cleaning crowns.")
        crowns = stitch_crowns(tiles_path + "predictions_geo/", 1)
        clean = clean_crowns(crowns, 0.6, confidence=0)
        clean = clean[clean["Confidence_score"] > float(self.settings['crown']['confidence'])]
        clean = clean.set_geometry(clean.simplify(0.3))
        clean.to_file(site_path + "/crowns_out.gpkg")

        predictions_img = self.overlay_image_with_gpkg(image_path, site_path + "/crowns_out.gpkg")
        self.logger.info("Image evaluation completed.")
        return predictions_img

    def plot_base_image(self, image_path):
        """
        Plot the base image.

        Args:
            image_path (Path): The path to the image to be plotted.

        Returns:
            tuple: The size of the base image.
        """
        self.logger.info(f"Plotting base image {image_path}")
        base_image = Image.open(image_path)
        plt.imshow(base_image)
        return base_image.size

    def plot_geopackage(self, gpkg_path, image_size):
        """
        Plot the GeoPackage geometries over the image.

        Args:
            gpkg_path (Path): The path to the GeoPackage file.
            image_size (tuple): The size of the base image.

        Returns:
            None
        """
        self.logger.info(f"Plotting GeoPackage geometries from {gpkg_path}")
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
        """
        Overlay the base image with GeoPackage geometries.

        Args:
            image_path (Path): The path to the base image.
            gpkg_path (Path): The path to the GeoPackage file containing geometries.

        Returns:
            Image: The image with the overlaid geometries.
        """
        self.logger.info(f"Overlaying image {image_path} with GeoPackage {gpkg_path}")
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

        self.logger.info("Overlay completed and image resized if necessary.")
        return img