import geemap
import ee
import os
from osgeo import gdal, osr

class GeoTIFFDownloader:
    def __init__(self, service_account, key_path):
        self.service_account = service_account
        self.key_path = key_path
        self.authenticate()

    def authenticate(self):
        credentials = ee.ServiceAccountCredentials(self.service_account, self.key_path)
        ee.Initialize(credentials)

    def set_area_of_interest(self, coordinates):
        self.aoi = ee.Geometry.Polygon(coordinates)

    def download_image(self, out_file, start_date="2020-01-01", end_date="2020-12-31"):
        collection = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") \
            .filterBounds(self.aoi) \
            .filterDate(start_date, end_date) \
            .sort("CLOUD_COVER") \
            .first()
        
        vis_params = {
            "bands": ["SR_B4", "SR_B3", "SR_B2"],
            "min": 0,
            "max": 3000,
            "gamma": 1.4,
        }

        # Clip the image to the area of interest and scale it
        clipped_image = collection.clip(self.aoi).visualize(**vis_params)

        # Download the clipped image
        geemap.ee_export_image(clipped_image, filename=out_file, scale=30, region=self.aoi, file_per_band=False, crs='EPSG:4326')

    def create_geotiff(self, image_file, geotiff_file):
        src_ds = gdal.Open(image_file)
        if src_ds is None:
            print("Unable to open image file.")
            return

        epsg = 4326  # WGS84
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(epsg)

        driver = gdal.GetDriverByName("GTiff")
        dst_ds = driver.CreateCopy(geotiff_file, src_ds, 0)
        dst_ds.SetProjection(srs.ExportToWkt())

        # Improved unpacking with error handling
        try:
            coordinates = self.aoi.bounds().getInfo()["coordinates"][0]
            min_lon, min_lat = coordinates[0]
            max_lon, max_lat = coordinates[2]
        except ValueError as e:
            print(f"Error unpacking coordinates: {e}")
            return

        x_res = (max_lon - min_lon) / src_ds.RasterXSize
        y_res = (min_lat - max_lat) / src_ds.RasterYSize
        geotransform = (min_lon, x_res, 0, max_lat, 0, y_res)
        dst_ds.SetGeoTransform(geotransform)

        src_ds = None
        dst_ds = None
        print(f"Georeferenced image saved as {geotiff_file}")
