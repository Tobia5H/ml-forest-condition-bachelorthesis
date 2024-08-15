from osgeo import gdal, osr

class GeoImageProcessor:
    def __init__(self):
        # Initialization without image-specific data
        self.dataset = None
        self.geotransform = None
        self.projection = None
        self.cols = None
        self.rows = None
        self.src_srs = None
        self.tgt_srs = None

    def load_image(self, image_path):
        self.dataset = gdal.Open(image_path)
        if self.dataset is None:
            raise FileNotFoundError(f"Unable to open image at {image_path}")
        
        self.geotransform = self.dataset.GetGeoTransform()
        self.projection = self.dataset.GetProjection()
        self.cols = self.dataset.RasterXSize
        self.rows = self.dataset.RasterYSize

        self.src_srs = osr.SpatialReference()
        self.src_srs.ImportFromWkt(self.projection)
        
        self.tgt_srs = osr.SpatialReference()
        self.tgt_srs.ImportFromEPSG(4326)  # WGS84 (EPSG:4326)

    def get_corners(self):
        minx = self.geotransform[0]
        maxx = minx + self.cols * self.geotransform[1]
        miny = self.geotransform[3] + self.rows * self.geotransform[5]
        maxy = self.geotransform[3]
        return (minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)

    def convert_to_latlon(self, easting, northing):
        transform = osr.CoordinateTransformation(self.src_srs, self.tgt_srs)
        lon, lat, _ = transform.TransformPoint(easting, northing)
        return lon, lat

    def process_image(self, image_path):
        self.load_image(image_path)
        
        corners = self.get_corners()
        converted_corners = [self.convert_to_latlon(corner[0], corner[1]) for corner in corners]
        
        # Print out the results
        print("Projection:", self.projection)
        print("Geotransform:", self.geotransform)
        print("Coordinates of the corners (in the format (lat, lng)):")
        print("Bottom-left:", converted_corners[0])
        print("Bottom-right:", converted_corners[1])
        print("Top-right:", converted_corners[2])
        print("Top-left:", converted_corners[3])
        
        return converted_corners
