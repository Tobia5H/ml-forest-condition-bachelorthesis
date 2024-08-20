from logger_config import LoggerConfig
import geopandas as gpd
import rasterio
import rasterio.mask
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import os

from image_converter import TifImageConverter

class VIAnalyzer:
    def __init__(self, output_dir):
        """
        Initializes the VIAnalyzer class.

        Args:
            output_dir (str): Path to the directory where output files will be saved.
        """
        self.logger = LoggerConfig.get_logger(self.__class__.__name__)
        self.tifconverter = TifImageConverter(output_directory='uploads/')
        self.shapefile_path = None
        self.vi_path = None
        self.gdf = None
        self.vi_image = None
        self.vi_meta = None
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

    def load_vi_image(self):
        """
        Loads the VI GeoTIFF image.

        Returns:
            tuple: A tuple containing the VI image array and its metadata.
        """
        self.logger.info(f"Loading VI image from {self.vi_path}.")
        
        with rasterio.open(self.vi_path) as src:
            self.vi_image = src.read(1)  # Read the first band
            self.vi_meta = src.meta

    def mask_vi_image(self):
        """
        Masks the VI image using the polygons from the shapefile.

        Returns:
            np.ndarray: The masked VI image array.

        Raises:
            ValueError: If the shapefile or VI image is not loaded.
        """
        if self.gdf is None or self.vi_image is None:
            self.logger.error("Shapefile or VI image not loaded.")
            raise ValueError("Shapefile or VI image not loaded.")

        self.logger.info("Masking VI image using shapefile polygons.")
        # Convert geometries in shapefile to the same CRS as the VI image
        self.gdf = self.gdf.to_crs(self.vi_meta['crs'])

        # Mask the VI image with the shapefile
        with rasterio.open(self.vi_path) as src:
            out_image, out_transform = rasterio.mask.mask(src, self.gdf.geometry, crop=True, all_touched=True)
            out_image = out_image[0]  # Extract the first band

        self.logger.info("VI image masked successfully.")
        return out_image

    def calculate_vi_statistics(self, masked_vi):
        """
        Calculates various statistics for the masked VI image.

        Args:
            masked_vi (np.ndarray): The masked VI image array.

        Returns:
            dict: A dictionary containing the mean, median, standard deviation, minimum, and maximum VI values.
        """
        self.logger.info("Calculating VI statistics.")
        vi_values = masked_vi[masked_vi > 0]  # Ignore zero values that are outside the polygons

        vi_stats = {
            'VI_mean': np.float64(np.mean(vi_values)),
            'VI_median': np.float64(np.median(vi_values)),
            'VI_std': np.float64(np.std(vi_values)),
            'VI_min': np.float64(np.min(vi_values).item()),
            'VI_max': np.float64(np.max(vi_values).item())
        }

        self.logger.info(f"VI statistics calculated: {vi_stats}")
        return vi_stats

    def plot_masked_vi(self, masked_vi, vi_name):
        """
        Plots the masked VI image and saves it as a PNG file in the outputs folder.

        Args:
            masked_vi (np.ndarray): The masked VI image array.
            vi_name (str): Name of the vegetation index (e.g., 'NDVI', 'EVI').
        """
        self.logger.info(f"Plotting masked {vi_name} image.")
        
        # Mask the VI array where values are not positive
        masked_array = np.ma.masked_where(masked_vi <= 0, masked_vi)
        
        # Create a colormap that ranges from dark green to light green
        cmap = plt.cm.YlGn
        cmap.set_bad(color='#bbbbbb')  # Set the masked values color to light gray (#bbbbbb)
        
        # Define the output file path
        output_file = os.path.join(self.output_dir, f"masked_{vi_name.lower()}.png")
        
        # Plot the VI image and save it to the specified path
        plt.figure(figsize=(10, 10))
        im = plt.imshow(masked_array, cmap=cmap)
        plt.title(f'Masked {vi_name} Image')
        cbar = plt.colorbar(im, label=f'{vi_name} Values')
        
        # Create a custom legend for the "not detected trees" (light gray) and valid VI (green) areas
        legend_elements = [
            Patch(facecolor='#bbbbbb', edgecolor='black', label='Areas without detected trees'),
            Patch(facecolor=cmap(0.75), edgecolor='black', label=f'Vegetated areas')
        ]
        plt.legend(handles=legend_elements, loc='lower right')

        plt.savefig(output_file, format='png')
        plt.close()  # Close the figure to prevent it from being displayed

        self.logger.info(f"Masked {vi_name} image saved as {output_file}.")

    def calculate(self, shapefile_path, vi_path, vi_name='NDVI'):
        """
        Executes the full VI analysis workflow.

        Args:
            shapefile_path (str): Path to the shapefile containing polygons.
            vi_path (str): Path to the VI GeoTIFF image.
            vi_name (str): Name of the vegetation index (e.g., 'NDVI', 'EVI'). Default is 'NDVI'.

        Returns:
            dict: A dictionary containing VI statistics.
        """
        self.logger.info(f"Starting {vi_name} analysis.")
        self.shapefile_path = shapefile_path
        self.vi_path = vi_path
        self.load_shapefile()
        self.load_vi_image()
        
        # Mask the VI image
        masked_vi = self.mask_vi_image()
        
        # Calculate VI statistics
        vi_stats = self.calculate_vi_statistics(masked_vi)
        
        # Plot VI values and save as png
        self.plot_masked_vi(masked_vi, vi_name)
        
        return vi_stats, masked_vi

    def combine_vi_masks(self, vi_masks, vi_weights):
        """
        Combines multiple vegetation index (VI) masks based on provided weights.

        Args:
            vi_masks (dict): Dictionary containing VI masks with their names as keys.
                            Example: {'ndvi': ndvi_mask, 'evi': evi_mask, ...}
            vi_weights (dict): Dictionary containing weights for each VI.
                            Example: {'ndvi': 0.2, 'evi': 0.2, ...}

        Returns:
            np.ndarray: The combined and weighted mask.
        """
        # Initialize combined mask with float64 precision
        combined_mask = np.zeros_like(next(iter(vi_masks.values())), dtype=np.float64)
        total_weight = sum(vi_weights.values())

        for vi_name, mask in vi_masks.items():
            weight = vi_weights.get(vi_name, 0)
            if weight > 0:
                # Normalize the mask to the range [0, 1]
                min_val = np.nanmin(mask)
                max_val = np.nanmax(mask)
                if max_val > min_val:
                    norm_mask = (mask - min_val) / (max_val - min_val)
                else:
                    norm_mask = np.zeros_like(mask, dtype=np.float64)  # Handle case where max_val == min_val
                
                # Apply weight and add to combined mask
                combined_mask += norm_mask * weight

        # Normalize the combined mask to ensure it falls within the range [0, 1]
        if total_weight > 0:
            combined_mask /= total_weight
        
        return combined_mask