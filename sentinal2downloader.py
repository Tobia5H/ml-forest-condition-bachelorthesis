import random
import ee
import requests
from datetime import datetime
from logger_config import LoggerConfig

class Sentinel2Downloader:
    def __init__(self):
        """Initialize the Earth Engine module with service account credentials."""
        self.logger = LoggerConfig.get_logger(self.__class__.__name__)
        credentials = ee.ServiceAccountCredentials(
            'python-script-azure-vm@ee-bachelorthesis-forestml.iam.gserviceaccount.com', 
            '/home/tobias/detectree2/keys/ee-bachelorthesis-forestml-9f670651e3e4.json'
        )
        ee.Initialize(credentials)
        self.logger.info("Earth Engine initialized with service account credentials.")

    def get_median_image(self, aoi, start_date, end_date):
        """Retrieve the median image from Sentinel-2 collection within the specified date range and AOI.
        
        :param aoi: Area of interest as an ee.Geometry object.
        :param start_date: Start date for filtering the image collection (YYYY-MM-DD).
        :param end_date: End date for filtering the image collection (YYYY-MM-DD).
        :return: Median image for the specified date range and AOI.
        """
        self.logger.info(f"Retrieving median image for AOI from {start_date} to {end_date}.")
        sentinel2 = ee.ImageCollection('COPERNICUS/S2_HARMONIZED') \
                       .filterDate(start_date, end_date) \
                       .filterBounds(aoi) \
                       .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10))  # Filter to get low-cloud images
        
        median_image = sentinel2.median().clip(aoi)
        self.logger.info("Median image retrieved successfully.")
        return median_image
    
    def get_rgb_download_url(self, aoi, start_date, end_date, scale=10, crs='EPSG:25833'):
        """Generate a download link for the true color RGB image.
        
        :param aoi: Area of interest as an ee.Geometry object.
        :param start_date: Start date for filtering the image collection (YYYY-MM-DD).
        :param end_date: End date for filtering the image collection (YYYY-MM-DD).
        :param scale: Spatial resolution of the output image in meters.
        :param crs: Coordinate Reference System for the output image.
        :return: URL link to download the RGB image.
        """
        self.logger.info("Generating RGB download URL.")
        median_image = self.get_median_image(aoi, start_date, end_date)
        rgb_image = median_image.select(['B4', 'B3', 'B2'])

        download_url = rgb_image.getDownloadURL({
            'scale': scale,  # Sentinel-2 RGB bands are at 10m resolution
            'region': aoi.getInfo()['coordinates'],
            'crs': crs,
            'format': 'GeoTIFF'
        })
        
        self.logger.info(f"RGB download URL generated: {download_url}")
        return download_url
    
    def get_ndvi_download_url(self, aoi, start_date, end_date, scale=10, crs='EPSG:25833'):
        """Generate a download link for the NDVI image.
        
        :param aoi: Area of interest as an ee.Geometry object.
        :param start_date: Start date for filtering the image collection (YYYY-MM-DD).
        :param end_date: End date for filtering the image collection (YYYY-MM-DD).
        :param scale: Spatial resolution of the output image in meters.
        :param crs: Coordinate Reference System for the output image.
        :return: URL link to download the NDVI image.
        """
        self.logger.info("Generating NDVI download URL.")
        median_image = self.get_median_image(aoi, start_date, end_date)
        ndvi_image = median_image.normalizedDifference(['B8', 'B4']).rename('NDVI')

        download_url = ndvi_image.getDownloadURL({
            'scale': scale,  # NDVI is calculated from 10m resolution bands
            'region': aoi.getInfo()['coordinates'],
            'crs': crs,
            'format': 'GeoTIFF'
        })
        
        self.logger.info(f"NDVI download URL generated: {download_url}")
        return download_url

    def download_nvdi_image(self, longitude_min, latitude_min, longitude_max, latitude_max, start_date, end_date):
        """Download links for NDVI image using the bounding box coordinates.
        
        :param longitude_min: Minimum longitude (west boundary of the area).
        :param latitude_min: Minimum latitude (south boundary of the area).
        :param longitude_max: Maximum longitude (east boundary of the area).
        :param latitude_max: Maximum latitude (north boundary of the area).
        :param start_date: Start date for filtering the image collection (YYYY-MM-DD).
        :param end_date: End date for filtering the image collection (YYYY-MM-DD).
        :return: File path to the downloaded image.
        """
        self.logger.info("Downloading NDVI image.")
        aoi = ee.Geometry.Rectangle([longitude_min, latitude_min, longitude_max, latitude_max])
        ndvi_url = self.get_ndvi_download_url(aoi=aoi, start_date=start_date, end_date=end_date)
        return self._get_image_with_request(ndvi_url, "ndvi")

    def download_rgb_image(self, longitude_min, latitude_min, longitude_max, latitude_max, start_date, end_date):
        """Download links for RGB image using the bounding box coordinates.
        
        :param longitude_min: Minimum longitude (west boundary of the area).
        :param latitude_min: Minimum latitude (south boundary of the area).
        :param longitude_max: Maximum longitude (east boundary of the area).
        :param latitude_max: Maximum latitude (north boundary of the area).
        :param start_date: Start date for filtering the image collection (YYYY-MM-DD).
        :param end_date: End date for filtering the image collection (YYYY-MM-DD).
        :return: File path to the downloaded image.
        """
        self.logger.info("Downloading RGB image.")
        aoi = ee.Geometry.Rectangle([longitude_min, latitude_min, longitude_max, latitude_max])
        rgb_url = self.get_rgb_download_url(aoi=aoi, start_date=start_date, end_date=end_date)
        return self._get_image_with_request(rgb_url, "rgb")
            
    def download_rgb_nvdi_image(self, longitude_min, latitude_min, longitude_max, latitude_max, start_date, end_date):
        """Download links for both RGB and NDVI images using the bounding box coordinates.
        
        :param longitude_min: Minimum longitude (west boundary of the area).
        :param latitude_min: Minimum latitude (south boundary of the area).
        :param longitude_max: Maximum longitude (east boundary of the area).
        :param latitude_max: Maximum latitude (north boundary of the area).
        :param start_date: Start date for filtering the image collection (YYYY-MM-DD).
        :param end_date: End date for filtering the image collection (YYYY-MM-DD).
        :return: File path to the downloaded images.
        """
        self.logger.info("Downloading both RGB and NDVI images.")
        nvdi_path = self.download_nvdi_image(longitude_min, latitude_min, longitude_max, latitude_max, start_date, end_date)
        rgb_path = self.download_rgb_image(longitude_min, latitude_min, longitude_max, latitude_max, start_date, end_date)
        return [rgb_path, nvdi_path]
            
    def _get_image_with_request(self, url, output_filename):
        """Helper method to download an image from a URL.
        
        :param url: The download URL for the image.
        :param output_filename: The output filename to save the image.
        :return: The path to the downloaded image file.
        """
        output_filename = f"uploads/{output_filename}.tif"
        self.logger.info(f"Downloading image from {url} to {output_filename}.")
        
        response = requests.get(url, stream=True)
        
        if response.status_code == 200:
            with open(output_filename, 'wb') as out_file:
                out_file.write(response.content)
            self.logger.info(f"Image successfully downloaded as {output_filename}")
            return output_filename
        else:
            self.logger.error(f"Failed to download image. Status code: {response.status_code}")
            return None
