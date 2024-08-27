import os
import shutil
import math
import aiohttp
import asyncio
from PIL import Image
from io import BytesIO
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from concurrent.futures import ThreadPoolExecutor
from logger_config import LoggerConfig

class BasemapDownloader:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(BasemapDownloader, cls).__new__(cls, *args, **kwargs)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, tile_size=256, output_dir="downloaded_tiles", crs="EPSG:3857"):
        """
        Initialize the BasemapDownloader with important variables.

        Args:
            tile_size (int, optional): The size of each tile in pixels. Defaults to 256.
            output_dir (str, optional): The directory where tiles will be saved. Defaults to "downloaded_tiles".
            crs (str, optional): The coordinate reference system for the output file. Defaults to "EPSG:3857".
        """
        if not self._initialized:
            self.tile_size = tile_size
            self.output_dir = output_dir
            self.crs = crs
            self.logger = LoggerConfig().get_logger(self.__class__.__name__)
            self._prepare_output_directory()
            self.logger.info("Basemap.at Downloader has been intialized successfully.")
            self.logger.info("This downloader uses the data source: basemap.at, which you can access under: https://basemap.at/")
            self._initialized = True

    def _prepare_output_directory(self):
        """
        Prepare the output directory by removing any existing content and recreating it.

        Returns:
            str: The path to the prepared directory.
        """
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        return self.output_dir

    def _calculate_tile_coordinates(self, lat_deg, lon_deg, zoom):
        """
        Calculate tile coordinates (x, y) for given geographic coordinates and zoom level.

        Args:
            lat_deg (float): Latitude in degrees.
            lon_deg (float): Longitude in degrees.
            zoom (int): Zoom level.

        Returns:
            tuple: A tuple containing the x and y tile coordinates.
        """
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** zoom
        x_tile = int((lon_deg + 180.0) / 360.0 * n)
        y_tile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
        return x_tile, y_tile

    def _calculate_tile_range(self, lat_min, lon_min, lat_max, lon_max, zoom):
        """
        Calculate the range of tiles needed to cover the area defined by the bounds.

        Args:
            lat_min (float): Minimum latitude (bottom edge of the rectangle).
            lon_min (float): Minimum longitude (left edge of the rectangle).
            lat_max (float): Maximum latitude (top edge of the rectangle).
            lon_max (float): Maximum longitude (right edge of the rectangle).
            zoom (int): Zoom level.

        Returns:
            tuple: A tuple containing the minimum and maximum tile x and y coordinates.
        """
        min_tile_x, min_tile_y = self._calculate_tile_coordinates(lat_max, lon_min, zoom)
        max_tile_x, max_tile_y = self._calculate_tile_coordinates(lat_min, lon_max, zoom)
        return min_tile_x, max_tile_x, min_tile_y, max_tile_y

    async def _download_tile_async(self, session, tile_url, x, y):
        """
        Asynchronously download a single tile image and save it to the specified output directory.

        Args:
            session (aiohttp.ClientSession): The aiohttp session for making HTTP requests.
            tile_url (str): The URL of the tile image to download.
            x (int): The x coordinate of the tile.
            y (int): The y coordinate of the tile.

        Returns:
            str or None: The path to the saved tile image, or None if the download failed.
        """
        try:
            async with session.get(tile_url) as response:
                if response.status == 200:
                    tile_image = Image.open(BytesIO(await response.read()))
                    tile_filename = f"tile_{x}_{y}.jpeg"
                    tile_path = os.path.join(self.output_dir, tile_filename)
                    tile_image.save(tile_path)
                    return tile_path
                else:
                    self.logger.error(f"Error: Received {response.status} for {tile_url}")
                    return None
        except Exception as e:
            self.logger.error(f"Error downloading {tile_url}: {str(e)}")
            return None

    async def _download_tiles_in_parallel_async(self, tile_urls):
        """
        Asynchronously download tiles in parallel and return a list of paths to the downloaded tiles.

        Args:
            tile_urls (list): A list of tuples containing the tile URL and its x and y coordinates.

        Returns:
            list: A list of paths to the downloaded tile images.
        """
        total_tiles = len(tile_urls)
        connector = aiohttp.TCPConnector(limit=20)  # Adjust limit as needed
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [
                self._download_tile_async(session, tile_url, x, y)
                for tile_url, x, y in tile_urls
            ]
            tile_paths = []
            for i, task in enumerate(asyncio.as_completed(tasks), 1):
                path = await task
                if path:
                    tile_paths.append(path)
                if i % 50 == 0 or i == total_tiles:
                    self.logger.info(f"Downloaded {i} of {total_tiles} tiles.")
            return tile_paths

    def download_tiles(self, lat_min, lon_min, lat_max, lon_max, zoom=19, layer="bmaporthofoto30cm", style="normal", tile_matrix_set="google3857", output_file="uploads/basemap_rgb.tif"):
        """
        Download and assemble tiles to cover the area defined by the bounds and save as a GeoTIFF file.

        Args:
            lat_min (float): Minimum latitude (bottom edge of the rectangle).
            lon_min (float): Minimum longitude (left edge of the rectangle).
            lat_max (float): Maximum latitude (top edge of the rectangle).
            lon_max (float): Maximum longitude (right edge of the rectangle).
            zoom (int, optional): Zoom level. Defaults to 19.
            layer (str, optional): The map layer to download tiles from. Defaults to "bmaporthofoto30cm".
            style (str, optional): The style of the map layer. Defaults to "normal".
            tile_matrix_set (str, optional): The tile matrix set. Defaults to "google3857".
            output_file (str, optional): The name of the output GeoTIFF file. Defaults to "uploads/basemap_rgb.tif".

        Returns:
            None
        """
        min_tile_x, max_tile_x, min_tile_y, max_tile_y = self._calculate_tile_range(lat_min, lon_min, lat_max, lon_max, zoom)
        total_tiles = (max_tile_x - min_tile_x + 1) * (max_tile_y - min_tile_y + 1)
        self.logger.info(f"Total number of required tiles: {total_tiles}")

        tile_urls = [
            (f"https://mapsneu.wien.gv.at/basemap/{layer}/{style}/{tile_matrix_set}/{zoom}/{y}/{x}.jpeg", x, y)
            for y in range(min_tile_y, max_tile_y + 1)
            for x in range(min_tile_x, max_tile_x + 1)
        ]

        tile_paths = asyncio.run(self._download_tiles_in_parallel_async(tile_urls))

        self.logger.info(f"Assembling image from {len(tile_paths)} tiles.")
        full_image = self._assemble_tiles(tile_paths, min_tile_x, max_tile_x, min_tile_y, max_tile_y)
        self.logger.info(f"Image successfully assembled from {len(tile_paths)} tiles.")
        
        self._save_as_geotiff(full_image, output_file, min_tile_x, max_tile_x, min_tile_y, max_tile_y)

        self._prepare_output_directory()
        self.logger.info(f"GeoTIFF saved as {output_file}")

    def _assemble_tiles(self, tile_paths, min_tile_x, max_tile_x, min_tile_y, max_tile_y):
        """
        Assemble the downloaded tiles into a single image.

        Args:
            tile_paths (list): A list of paths to the downloaded tile images.
            min_tile_x (int): Minimum tile x coordinate.
            max_tile_x (int): Maximum tile x coordinate.
            min_tile_y (int): Minimum tile y coordinate.
            max_tile_y (int): Maximum tile y coordinate.

        Returns:
            PIL.Image.Image: The assembled image.
        """
        full_image = Image.new('RGB', ((max_tile_x - min_tile_x + 1) * self.tile_size, (max_tile_y - min_tile_y + 1) * self.tile_size))
        for tile_path in tile_paths:
            x, y = map(int, os.path.splitext(os.path.basename(tile_path))[0].split('_')[1:])
            tile_image = Image.open(tile_path)
            full_image.paste(tile_image, ((x - min_tile_x) * self.tile_size, (y - min_tile_y) * self.tile_size))
            os.remove(tile_path)
        return full_image

    def _save_as_geotiff(self, full_image, output_file, min_tile_x, max_tile_x, min_tile_y, max_tile_y):
        """
        Save the assembled image as a GeoTIFF file.

        Args:
            full_image (PIL.Image.Image): The assembled image.
            output_file (str): The name of the output GeoTIFF file.
            min_tile_x (int): Minimum tile x coordinate.
            max_tile_x (int): Maximum tile x coordinate.
            min_tile_y (int): Minimum tile y coordinate.
            max_tile_y (int): Maximum tile y coordinate.

        Returns:
            None
        """
        image_array = np.array(full_image)
        west = min_tile_x * self.tile_size
        north = min_tile_y * self.tile_size
        east = (max_tile_x + 1) * self.tile_size
        south = (max_tile_y + 1) * self.tile_size

        transform = from_bounds(west, south, east, north, full_image.width, full_image.height)

        with rasterio.open(output_file, 'w', driver='GTiff', height=full_image.height, width=full_image.width, count=3,
                           dtype=image_array.dtype, crs=self.crs, transform=transform) as dst:
            for i in range(3):
                dst.write(image_array[:, :, i], i + 1)
