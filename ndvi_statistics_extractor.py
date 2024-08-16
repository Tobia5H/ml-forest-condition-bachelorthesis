from logger_config import LoggerConfig
import geopandas as gpd
import rasterio
import rasterio.mask
import numpy as np
import matplotlib.pyplot as plt

from image_converter import TifImageConverter

class NDVIAnalyzer:
    def __init__(self):
        """
        Initializes the NDVIAnalyzer class.

        Attributes:
            shapefile_path (str): Path to the shapefile containing polygons.
            ndvi_path (str): Path to the NDVI GeoTIFF image.
            gdf (geopandas.GeoDataFrame): Geodataframe containing the loaded polygons.
            ndvi_image (np.ndarray): Array representation of the NDVI image.
            ndvi_meta (dict): Metadata of the NDVI GeoTIFF image.
        """
        self.logger = LoggerConfig.get_logger(self.__class__.__name__)
        self.tifconverter = TifImageConverter(output_directory='uploads/')
        self.shapefile_path = None
        self.ndvi_path = None
        self.gdf = None
        self.ndvi_image = None
        self.ndvi_meta = None

    def load_shapefile(self):
        """
        Loads the shapefile containing the polygons.

        Returns:
            geopandas.GeoDataFrame: Geodataframe containing the loaded polygons.
        """
        self.logger.info(f"Loading shapefile from {self.shapefile_path}.")
        self.gdf = gpd.read_file(self.shapefile_path)
        return self.gdf

    def load_ndvi_image(self):
        """
        Loads the NDVI GeoTIFF image.

        Returns:
            tuple: A tuple containing the NDVI image array and its metadata.
        """
        self.logger.info(f"Loading NDVI image from {self.ndvi_path}.")
        self.ndvi_path = self.tifconverter.convert_to_uint8(self.ndvi_path)
        
        with rasterio.open(self.ndvi_path) as src:
            self.ndvi_image = src.read(1)  # Read the first band
            self.ndvi_meta = src.meta
        return self.ndvi_image, self.ndvi_meta

    def mask_ndvi_image(self):
        """
        Masks the NDVI image using the polygons from the shapefile.

        Returns:
            np.ndarray: The masked NDVI image array.
        """
        if self.gdf is None or self.ndvi_image is None:
            self.logger.error("Shapefile or NDVI image not loaded.")
            raise ValueError("Shapefile or NDVI image not loaded.")

        self.logger.info("Masking NDVI image using shapefile polygons.")
        # Convert geometries in shapefile to the same CRS as the NDVI image
        self.gdf = self.gdf.to_crs(self.ndvi_meta['crs'])

        # Mask the NDVI image with the shapefile
        with rasterio.open(self.ndvi_path) as src:
            out_image, out_transform = rasterio.mask.mask(src, self.gdf.geometry, crop=True, all_touched=True)
            out_image = out_image[0]  # Extract the first band

        self.logger.info("NDVI image masked successfully.")
        return out_image

    def calculate_ndvi_statistics(self, masked_ndvi):
        """
        Calculates various statistics for the masked NDVI image.

        Args:
            masked_ndvi (np.ndarray): The masked NDVI image array.

        Returns:
            dict: A dictionary containing the mean, median, standard deviation, minimum, and maximum NDVI values.
        """
        self.logger.info("Calculating NDVI statistics.")
        ndvi_values = masked_ndvi[masked_ndvi > 0]  # Ignore zero values that are outside the polygons

        ndvi_stats = {
            'NDVI_mean': np.mean(ndvi_values),
            'NDVI_median': np.median(ndvi_values),
            'NDVI_std': np.std(ndvi_values),
            'NDVI_min': np.min(ndvi_values),
            'NDVI_max': np.max(ndvi_values)
        }

        self.logger.info(f"NDVI statistics calculated: {ndvi_stats}")
        return ndvi_stats

    def plot_masked_ndvi(self, masked_ndvi):
        """
        Plots the masked NDVI image.

        Args:
            masked_ndvi (np.ndarray): The masked NDVI image array.
        """
        self.logger.info("Plotting masked NDVI image.")
        masked_array = np.ma.masked_where(masked_ndvi <= 0, masked_ndvi)
        cmap = plt.cm.gray
        cmap.set_bad(color='pink')
        
        plt.figure(figsize=(10, 10))
        plt.imshow(masked_array, cmap=cmap)
        plt.title('Masked NDVI Image')
        plt.colorbar(label='NDVI Values')
        plt.show()

    def calculate(self, shapefile_path, ndvi_path):
        """
        Executes the full NDVI analysis workflow.

        Args:
            shapefile_path (str): Path to the shapefile containing polygons.
            ndvi_path (str): Path to the NDVI GeoTIFF image.

        Returns:
            dict: A dictionary containing NDVI statistics.
        """
        self.logger.info("Starting NDVI analysis.")
        self.shapefile_path = shapefile_path
        self.ndvi_path = ndvi_path
        self.load_shapefile()
        self.load_ndvi_image()
        
        # Mask the NDVI image
        masked_ndvi = self.mask_ndvi_image()
        
        # Calculate NDVI statistics
        return self.calculate_ndvi_statistics(masked_ndvi)

