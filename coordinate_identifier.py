from osgeo import gdal, osr
from logger_config import LoggerConfig

class GeoImageProcessor:
    def __init__(self):
        """
        Initializes the GeoImageProcessor class.

        Attributes:
            dataset (gdal.Dataset): The loaded GDAL dataset.
            geotransform (tuple): The geotransform information of the dataset.
            projection (str): The projection information of the dataset in WKT format.
            cols (int): Number of columns (width) of the dataset.
            rows (int): Number of rows (height) of the dataset.
            src_srs (osr.SpatialReference): The spatial reference of the source projection.
            tgt_srs (osr.SpatialReference): The target spatial reference, WGS84 (EPSG:4326).
        """
        self.logger = LoggerConfig.get_logger(self.__class__.__name__)
        self.dataset = None
        self.geotransform = None
        self.projection = None
        self.cols = None
        self.rows = None
        self.src_srs = None
        self.tgt_srs = None

    def load_image(self, image_path):
        """
        Loads the image and extracts geospatial information.

        Args:
            image_path (str): The file path to the image.

        Raises:
            FileNotFoundError: If the image cannot be opened.

        Returns:
            None
        """
        self.logger.info(f"Loading image from {image_path}")
        self.dataset = gdal.Open(image_path)
        if self.dataset is None:
            self.logger.error(f"Unable to open image at {image_path}")
            raise FileNotFoundError(f"Unable to open image at {image_path}")
        
        self.geotransform = self.dataset.GetGeoTransform()
        self.projection = self.dataset.GetProjection()
        self.cols = self.dataset.RasterXSize
        self.rows = self.dataset.RasterYSize

        self.src_srs = osr.SpatialReference()
        self.src_srs.ImportFromWkt(self.projection)
        
        self.tgt_srs = osr.SpatialReference()
        self.tgt_srs.ImportFromEPSG(4326)  # WGS84 (EPSG:4326)
        self.logger.info("Image loaded and geospatial information extracted.")

    def get_corners(self):
        """
        Retrieves the corner coordinates of the image in the source projection.

        Returns:
            tuple: A tuple containing four corners of the image in the source projection, 
                   formatted as ((minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)).
        """
        self.logger.info("Calculating corner coordinates.")
        minx = self.geotransform[0]
        maxx = minx + self.cols * self.geotransform[1]
        miny = self.geotransform[3] + self.rows * self.geotransform[5]
        maxy = self.geotransform[3]
        return (minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)

    def convert_to_latlon(self, easting, northing):
        """
        Converts coordinates from the source projection to latitude and longitude (WGS84).

        Args:
            easting (float): The easting coordinate in the source projection.
            northing (float): The northing coordinate in the source projection.

        Returns:
            tuple: A tuple containing the longitude and latitude.
        """
        self.logger.info(f"Converting coordinates ({easting}, {northing}) to latitude and longitude.")
        transform = osr.CoordinateTransformation(self.src_srs, self.tgt_srs)
        lon, lat, _ = transform.TransformPoint(easting, northing)
        self.logger.info(f"Converted to (lon, lat): ({lon}, {lat})")
        return lon, lat

    def process_image(self, image_path):
        """
        Processes the image by loading it, extracting corner coordinates, 
        and converting them to latitude and longitude.

        Args:
            image_path (str): The file path to the image.

        Returns:
            list: A list of tuples containing the latitude and longitude of the image corners.
        """
        self.logger.info(f"Processing image at {image_path}")
        self.load_image(image_path)
        
        corners = self.get_corners()
        converted_corners = [self.convert_to_latlon(corner[0], corner[1]) for corner in corners]
        
        return converted_corners
