
import ee
import requests
from logger_config import LoggerConfig

class Sentinel2Downloader:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Sentinel2Downloader, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.logger = LoggerConfig().get_logger(self.__class__.__name__)
            credentials = ee.ServiceAccountCredentials(
                'python-script-azure-vm@ee-bachelorthesis-forestml.iam.gserviceaccount.com', 
                'keys/ee-bachelorthesis-forestml-9f670651e3e4.json'
            )
            ee.Initialize(credentials)
            self.logger.info("Earth Engine initialized with service account credentials.")
            self._initialized = True

    def get_median_image(self, aoi, start_date, end_date):
        """Retrieve the median image from Sentinel-2 collection within the specified date range and AOI.
        
        Args:
            aoi (ee.Geometry): Area of interest as an ee.Geometry object.
            start_date (str): Start date for filtering the image collection (YYYY-MM-DD).
            end_date (str): End date for filtering the image collection (YYYY-MM-DD).
        
        Returns:
            ee.Image: Median image for the specified date range and AOI.
        """
        self.logger.info(f"Retrieving median image for AOI from {start_date} to {end_date}.")
        
        # Filter to ensure images are taken during daylight
        solar_elevation_filter = ee.Filter.gt('MEAN_SOLAR_ZENITH_ANGLE', 0)  # Ensure daylight by positive solar elevation
        
        sentinel2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                    .filterDate(start_date, end_date) \
                    .filterBounds(aoi) \
                    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10)) \
                    .filter(solar_elevation_filter)  # Filter for daylight images
        
        median_image = sentinel2.median().clip(aoi)
        self.logger.info("Median image retrieved successfully.")
        return median_image

    
    def get_rgb_download_url(self, aoi, start_date, end_date, scale=10, crs='EPSG:25833'):
        """Generate a download link for the true color RGB image.
        
        Args:
            aoi (ee.Geometry): Area of interest as an ee.Geometry object.
            start_date (str): Start date for filtering the image collection (YYYY-MM-DD).
            end_date (str): End date for filtering the image collection (YYYY-MM-DD).
            scale (int, optional): Spatial resolution of the output image in meters. Default is 10.
            crs (str, optional): Coordinate Reference System for the output image. Default is 'EPSG:25833'.
        
        Returns:
            str: URL link to download the RGB image.
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
        
        Args:
            aoi (ee.Geometry): Area of interest as an ee.Geometry object.
            start_date (str): Start date for filtering the image collection (YYYY-MM-DD).
            end_date (str): End date for filtering the image collection (YYYY-MM-DD).
            scale (int, optional): Spatial resolution of the output image in meters. Default is 10.
            crs (str, optional): Coordinate Reference System for the output image. Default is 'EPSG:25833'.
        
        Returns:
            str: URL link to download the NDVI image.
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
    
    def get_evi_download_url(self, aoi, start_date, end_date, scale=10, crs='EPSG:25833'):
        """Generate a download link for the EVI image.
        
        Args:
            aoi (ee.Geometry): Area of interest as an ee.Geometry object.
            start_date (str): Start date for filtering the image collection (YYYY-MM-DD).
            end_date (str): End date for filtering the image collection (YYYY-MM-DD).
            scale (int, optional): Spatial resolution of the output image in meters. Default is 10.
            crs (str, optional): Coordinate Reference System for the output image. Default is 'EPSG:25833'.
        
        Returns:
            str: URL link to download the EVI image.
        """
        self.logger.info("Generating EVI download URL.")
        median_image = self.get_median_image(aoi, start_date, end_date)
        
        evi_image = median_image.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
            {
                'NIR': median_image.select('B8'),
                'RED': median_image.select('B4'),
                'BLUE': median_image.select('B2')
            }
        ).rename('EVI')
        
        download_url = evi_image.getDownloadURL({
            'scale': scale,
            'region': aoi.getInfo()['coordinates'],
            'crs': crs,
            'format': 'GeoTIFF'
        })
        
        self.logger.info(f"EVI download URL generated: {download_url}")
        return download_url

    def get_gndvi_download_url(self, aoi, start_date, end_date, scale=10, crs='EPSG:25833'):
        """Generate a download link for the GNDVI image.
        
        Args:
            aoi (ee.Geometry): Area of interest as an ee.Geometry object.
            start_date (str): Start date for filtering the image collection (YYYY-MM-DD).
            end_date (str): End date for filtering the image collection (YYYY-MM-DD).
            scale (int, optional): Spatial resolution of the output image in meters. Default is 10.
            crs (str, optional): Coordinate Reference System for the output image. Default is 'EPSG:25833'.
        
        Returns:
            str: URL link to download the GNDVI image.
        """
        self.logger.info("Generating GNDVI download URL.")
        median_image = self.get_median_image(aoi, start_date, end_date)
        gndvi_image = median_image.normalizedDifference(['B8', 'B3']).rename('GNDVI')

        download_url = gndvi_image.getDownloadURL({
            'scale': scale,
            'region': aoi.getInfo()['coordinates'],
            'crs': crs,
            'format': 'GeoTIFF'
        })
        
        self.logger.info(f"GNDVI download URL generated: {download_url}")
        return download_url

    def get_chlorophyll_index_download_url(self, aoi, start_date, end_date, scale=10, crs='EPSG:25833', index_type='green'):
        """Generate a download link for the Chlorophyll Index image.
        
        Args:
            aoi (ee.Geometry): Area of interest as an ee.Geometry object.
            start_date (str): Start date for filtering the image collection (YYYY-MM-DD).
            end_date (str): End date for filtering the image collection (YYYY-MM-DD).
            scale (int, optional): Spatial resolution of the output image in meters. Default is 10.
            crs (str, optional): Coordinate Reference System for the output image. Default is 'EPSG:25833'.
            index_type (str, optional): Type of Chlorophyll Index ('green' or 'red-edge'). Default is 'green'.
        
        Returns:
            str: URL link to download the Chlorophyll Index image.
        """
        self.logger.info(f"Generating Chlorophyll Index ({index_type}) download URL.")
        median_image = self.get_median_image(aoi, start_date, end_date)
        
        if index_type == 'green':
            chlorophyll_index_image = median_image.expression(
                '(NIR / GREEN) - 1',
                {
                    'NIR': median_image.select('B8'),
                    'GREEN': median_image.select('B3')
                }
            ).rename('CIgreen')
        elif index_type == 'red-edge':
            chlorophyll_index_image = median_image.expression(
                '(NIR / REDEDGE) - 1',
                {
                    'NIR': median_image.select('B8'),
                    'REDEDGE': median_image.select('B5')
                }
            ).rename('CIred-edge')
        else:
            raise ValueError("Invalid index_type. Use 'green' or 'red-edge'.")
        
        download_url = chlorophyll_index_image.getDownloadURL({
            'scale': scale,
            'region': aoi.getInfo()['coordinates'],
            'crs': crs,
            'format': 'GeoTIFF'
        })
        
        self.logger.info(f"Chlorophyll Index ({index_type}) download URL generated: {download_url}")
        return download_url


    def download_nvdi_image(self, longitude_min, latitude_min, longitude_max, latitude_max, start_date, end_date, crs='EPSG:25833'):
        """Download links for NDVI image using the bounding box coordinates.
        
        Args:
            longitude_min (float): Minimum longitude (west boundary of the area).
            latitude_min (float): Minimum latitude (south boundary of the area).
            longitude_max (float): Maximum longitude (east boundary of the area).
            latitude_max (float): Maximum latitude (north boundary of the area).
            start_date (str): Start date for filtering the image collection (YYYY-MM-DD).
            end_date (str): End date for filtering the image collection (YYYY-MM-DD).
            crs (str, optional): Coordinate Reference System for the output image. Default is 'EPSG:25833'.
        
        Returns:
            str: File path to the downloaded image.
        """
        self.logger.info("Downloading NDVI image.")
        aoi = ee.Geometry.Rectangle([longitude_min, latitude_min, longitude_max, latitude_max])
        ndvi_url = self.get_ndvi_download_url(aoi=aoi, start_date=start_date, end_date=end_date, crs=crs)
        return self._get_image_with_request(ndvi_url, "ndvi")

    def download_rgb_image(self, longitude_min, latitude_min, longitude_max, latitude_max, start_date, end_date, crs='EPSG:25833'):
        """Download links for RGB image using the bounding box coordinates.
        
        Args:
            longitude_min (float): Minimum longitude (west boundary of the area).
            latitude_min (float): Minimum latitude (south boundary of the area).
            longitude_max (float): Maximum longitude (east boundary of the area).
            latitude_max (float): Maximum latitude (north boundary of the area).
            start_date (str): Start date for filtering the image collection (YYYY-MM-DD).
            end_date (str): End date for filtering the image collection (YYYY-MM-DD).
            crs (str, optional): Coordinate Reference System for the output image. Default is 'EPSG:25833'.
        
        Returns:
            str: File path to the downloaded image.
        """
        self.logger.info("Downloading RGB image.")
        aoi = ee.Geometry.Rectangle([longitude_min, latitude_min, longitude_max, latitude_max])
        rgb_url = self.get_rgb_download_url(aoi=aoi, start_date=start_date, end_date=end_date, crs=crs)
        return self._get_image_with_request(rgb_url, "rgb")
    
    def download_evi_image(self, longitude_min, latitude_min, longitude_max, latitude_max, start_date, end_date, crs='EPSG:25833'):
        self.logger.info("Downloading EVI image.")
        aoi = ee.Geometry.Rectangle([longitude_min, latitude_min, longitude_max, latitude_max])
        evi_url = self.get_evi_download_url(aoi=aoi, start_date=start_date, end_date=end_date, crs=crs)
        return self._get_image_with_request(evi_url, "evi")

    def download_gndvi_image(self, longitude_min, latitude_min, longitude_max, latitude_max, start_date, end_date, crs='EPSG:25833'):
        self.logger.info("Downloading GNDVI image.")
        aoi = ee.Geometry.Rectangle([longitude_min, latitude_min, longitude_max, latitude_max])
        gndvi_url = self.get_gndvi_download_url(aoi=aoi, start_date=start_date, end_date=end_date, crs=crs)
        return self._get_image_with_request(gndvi_url, "gndvi")

    def download_chlorophyll_index_image(self, longitude_min, latitude_min, longitude_max, latitude_max, start_date, end_date, crs='EPSG:25833', index_type='green'):
        self.logger.info(f"Downloading Chlorophyll Index ({index_type}) image.")
        aoi = ee.Geometry.Rectangle([longitude_min, latitude_min, longitude_max, latitude_max])
        ci_url = self.get_chlorophyll_index_download_url(aoi=aoi, start_date=start_date, end_date=end_date, crs=crs, index_type=index_type)
        return self._get_image_with_request(ci_url, f"chlorophyll_{index_type}")

            
    def _get_image_with_request(self, url, output_filename):
        """Helper method to download an image from a URL.
        
        Args:
            url (str): The download URL for the image.
            output_filename (str): The output filename to save the image.
        
        Returns:
            str: The path to the downloaded image file, or None if the download failed.
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
