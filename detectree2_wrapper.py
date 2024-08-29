from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import geopandas as gpd
import rasterio
import io
import os
import psutil

from detectree2.preprocessing.tiling import tile_data
from detectree2.models.outputs import project_to_geojson, stitch_crowns, clean_crowns
from detectree2.models.predict import predict_on_data
from detectree2.models.train import setup_cfg
from detectron2.engine import DefaultPredictor
import torch

from logger_config import LoggerConfig

class Detectree2:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Detectree2, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, settings):
        if not self._initialized:
            self.logger = LoggerConfig().get_logger(self.__class__.__name__)
            self.settings = settings
            if torch.cuda.is_available():
                self.cudaAvailable = True
                self.logger.info(f"CUDA has been detected. Your GPU is: {torch.cuda.get_device_name(0)}. Calculations will be performed on {torch.cuda.get_device_name(0)}")
            else:
                self.cudaAvailable = False
                self.logger.info("CUDA has NOT been detected. No compatible NVIDIA GPU found. Calculations will be performed on your CPU.")
                
            self.logger.info(f"Detectree2 initialized with settings: {settings}")
            self._initialized = True

    def load_model(self, model_path):
        """
        Loads the model configuration.

        Args:
            model_path (Path): The path to the model configuration file.

        Returns:
            cfg: The loaded model configuration.
        """
        self.logger.info(f"Loading model from {model_path}")
        cfg = setup_cfg(update_model=str(model_path))
        if self.cudaAvailable:
            cfg.MODEL.DEVICE = "cuda"
        else:
            cfg.MODEL.DEVICE = "cpu"
        self.logger.info(f"Model configuration loaded and device set to {cfg.MODEL.DEVICE}")
        return cfg

    def evaluate_image(self, image_path, model_path):
        """
        Evaluates an image using the provided model.

        Args:
            image_path (Path): The path to the image to be evaluated.
            model_path (Path): The path to the model configuration.

        Returns:
            Image: The resulting image with overlaid predictions.

        Raises:
            ValueError: If the image file format is unsupported.
            RuntimeError: If the tile size is too big for the virtual machine.
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

        if self._check_tile_size(tiles_path) or self.cudaAvailable:
            self.logger.info("Predicting on the tiled data.")
            predict_on_data(tiles_path, predictor=DefaultPredictor(cfg))
        else:
            raise RuntimeError("Tile size is too big for this VM. Please decrease tile size and try again.")

        project_to_geojson(tiles_path, tiles_path + "predictions/", tiles_path + "predictions_geo/")
        self.logger.info("Stitching and cleaning crowns.")

        crown_confidence = float(self.settings['crown']['confidence'])
        crowns = stitch_crowns(tiles_path + "predictions_geo/", 1)
        if not crowns.empty:
            clean = clean_crowns(crowns, 0.6, crown_confidence)
            clean = clean[clean["Confidence_score"] > float(self.settings['crown']['confidence'])]
            clean = clean.set_geometry(clean.simplify(0.3))
            clean.to_file(site_path + "/crowns_out.gpkg")
            predictions_img = self.overlay_image_with_gpkg(image_path, site_path + "/crowns_out.gpkg")
        else:
            raise ValueError("No tree crowns were detected in the image.")
        
        self.logger.info("Image evaluation completed.")
        return predictions_img

    def plot_base_image(self, image_path):
        """
        Plots the base image.

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
        Plots the GeoPackage geometries over the image.

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
        Overlays the base image with GeoPackage geometries.

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

    def _check_tile_size(self, folder_path):
        """
        Checks if the tile size is appropriate for the available memory.

        Args:
            folder_path (str): Path to the folder containing the tiles.

        Returns:
            bool: True if the tile size is appropriate, False otherwise.
        """
        available_memory = psutil.virtual_memory().available
        tif_files = [f for f in os.listdir(folder_path) if f.endswith('.tif')]
        tif_sizes = [(f, os.path.getsize(os.path.join(folder_path, f))) for f in tif_files]
        tif_sizes.sort(key=lambda x: x[1], reverse=True)

        max_size = 0.06 * available_memory

        if tif_sizes and tif_sizes[0][1] > max_size:
            return False

        if len(tif_sizes) > 1 and (tif_sizes[0][1] + tif_sizes[1][1]) > 180 * 1024 * 1024:
            return False

        return True
