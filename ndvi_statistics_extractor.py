from logger_config import LoggerConfig
import geopandas as gpd
import rasterio
import rasterio.mask
import numpy as np
import matplotlib.pyplot as plt
import os

from image_converter import TifImageConverter

class NDVIAnalyzer:
    def __init__(self, output_dir):
        """
        Initializes the NDVIAnalyzer class.

        Args:
            output_dir (str): Path to the directory where output files will be saved.
        """
        self.logger = LoggerConfig.get_logger(self.__class__.__name__)
        self.tifconverter = TifImageConverter(output_directory='uploads/')
        self.shapefile_path = None
        self.ndvi_path = None
        self.gdf = None
        self.ndvi_image = None
        self.ndvi_meta = None
        self.output_dir = output_dir

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

        Raises:
            ValueError: If the shapefile or NDVI image is not loaded.
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
            'NDVI_min': np.min(ndvi_values).item(),
            'NDVI_max': np.max(ndvi_values).item()
        }

        self.logger.info(f"NDVI statistics calculated: {ndvi_stats}")
        return ndvi_stats

    def plot_masked_ndvi(self, masked_ndvi):
        """
        Plots the masked NDVI image and saves it as a PNG file in the outputs folder.

        Args:
            masked_ndvi (np.ndarray): The masked NDVI image array.
        """
        self.logger.info("Plotting masked NDVI image.")
        
        # Mask the NDVI array where values are not positive
        masked_array = np.ma.masked_where(masked_ndvi <= 0, masked_ndvi)
        
        # Create a colormap that ranges from dark green to light green
        cmap = plt.cm.YlGn
        cmap.set_bad(color='#bbbbbb')  # Set the masked values color to light gray (#bbbbbb)
        
        # Define the output file path
        output_file = os.path.join(self.output_dir, "masked_ndvi.png")
        
        # Plot the NDVI image and save it to the specified path
        plt.figure(figsize=(10, 10))
        im = plt.imshow(masked_array, cmap=cmap)
        plt.title('Masked NDVI Image')
        cbar = plt.colorbar(im, label='NDVI Values')
        
        # Create a custom legend for the "not detected trees" (light gray) and valid NDVI (green) areas
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#bbbbbb', edgecolor='black', label='Areas without detected trees (NDVI <= 0)'),
            Patch(facecolor=cmap(0.75), edgecolor='black', label='Vegetated areas (NDVI > 0)')
        ]
        plt.legend(handles=legend_elements, loc='lower right')

        plt.savefig(output_file, format='png')
        plt.close()  # Close the figure to prevent it from being displayed

        self.logger.info(f"Masked NDVI image saved as {output_file}.")

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
        ndvi_stats = self.calculate_ndvi_statistics(masked_ndvi)
        
        # Plot NDVI values and save as png
        self.plot_masked_ndvi(masked_ndvi)
        
        return ndvi_stats
