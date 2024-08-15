import geopandas as gpd
import rasterio
import rasterio.mask
import numpy as np
import matplotlib.pyplot as plt

class NDVIAnalyzer:
    def __init__(self):
        """
        Initializes the NDVIAnalyzer class.
        """
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
        self.gdf = gpd.read_file(self.shapefile_path)
        return self.gdf

    def load_ndvi_image(self):
        """
        Loads the NDVI GeoTIFF image.

        Returns:
            tuple: A tuple containing the NDVI image array and its metadata.
        """
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
            raise ValueError("Shapefile or NDVI image not loaded.")

        # Convert geometries in shapefile to the same CRS as the NDVI image
        self.gdf = self.gdf.to_crs(self.ndvi_meta['crs'])

        # Mask the NDVI image with the shapefile
        with rasterio.open(self.ndvi_path) as src:
            out_image, out_transform = rasterio.mask.mask(src, self.gdf.geometry, crop=True, all_touched=True)
            out_image = out_image[0]  # Extract the first band

        return out_image

    def calculate_ndvi_statistics(self, masked_ndvi):
        """
        Calculates various statistics for the masked NDVI image.

        Args:
            masked_ndvi (np.ndarray): The masked NDVI image array.

        Returns:
            dict: A dictionary containing the mean, median, standard deviation, minimum, and maximum NDVI values.
        """
        ndvi_values = masked_ndvi[masked_ndvi > 0]  # Ignore zero values that are outside the polygons

        ndvi_stats = {
            'NDVI_mean': np.mean(ndvi_values),
            'NDVI_median': np.median(ndvi_values),
            'NDVI_std': np.std(ndvi_values),
            'NDVI_min': np.min(ndvi_values),
            'NDVI_max': np.max(ndvi_values)
        }

        return ndvi_stats

    def plot_masked_ndvi(self, masked_ndvi):
        """
        Plots the masked NDVI image.

        Args:
            masked_ndvi (np.ndarray): The masked NDVI image array.
        """
        masked_array = np.ma.masked_where(masked_ndvi <= 0, masked_ndvi)
        cmap = plt.cm.gray
        cmap.set_bad(color='pink')
        
        plt.figure(figsize=(10, 10))
        plt.imshow(masked_array, cmap=cmap)
        plt.title('Masked NDVI Image')
        plt.colorbar(label='NDVI Values')
        plt.show()
        
    def calculate(self, shapefile_path, ndvi_path):
        self.shapefile_path = shapefile_path
        self.ndvi_image = ndvi_path
        self.load_shapefile()
        self.load_ndvi_image()
        
        # Mask the NDVI image
        masked_ndvi = self.mask_ndvi_image()
        
        # Calculate NDVI statistics
        return self.calculate_ndvi_statistics(masked_ndvi)


# Example usage:
# if __name__ == "__main__":
#     shapefile_path = 'outputs/crowns_out.gpkg'
#     ndvi_path = 'uploads/ndvi_20240815_22622.tif'

#     analyzer = NDVIAnalyzer(shapefile_path, ndvi_path)
    
#     # Load data
#     analyzer.load_shapefile()
#     analyzer.load_ndvi_image()
    
#     # Mask the NDVI image
#     masked_ndvi = analyzer.mask_ndvi_image()
    
#     # Calculate NDVI statistics
#     stats = analyzer.calculate_ndvi_statistics(masked_ndvi)
#     print(f"NDVI Mean: {stats['NDVI_mean']}")
#     print(f"NDVI Median: {stats['NDVI_median']}")
#     print(f"NDVI Standard Deviation: {stats['NDVI_std']}")
#     print(f"NDVI Minimum: {stats['NDVI_min']}")
#     print(f"NDVI Maximum: {stats['NDVI_max']}")
    
#     # Plot the masked NDVI image
#     analyzer.plot_masked_ndvi(masked_ndvi)
