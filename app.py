from flask import Flask, render_template, request, send_from_directory, jsonify
from pathlib import Path
from werkzeug.utils import secure_filename
import os
import shutil
import rasterio
from datetime import datetime, timedelta

from detectree2_wrapper import Detectree2
from coordinate_identifier import GeoImageProcessor
from sentinal2downloader import Sentinel2Downloader
from image_converter import TifImageConverter
from ndvi_statistics_extractor import NDVIAnalyzer
from logger_config import LoggerConfig


class FlaskAppWrapper:
    def __init__(self):
        """
        Initializes the Flask application and all required components.
        """
        self.app = Flask(__name__)
        self.logger = LoggerConfig.get_logger(self.__class__.__name__, log_to_file=True)

        # Define folder paths and allowed file extensions
        self.UPLOAD_FOLDER = 'uploads/'
        self.OUTPUT_FOLDER = 'outputs/'
        self.DISPLAY_FOLDER = 'display/'
        self.current_path = os.path.abspath(os.getcwd())
        self.folder_name = 'tilespred/'
        self.TILES_FOLDER = os.path.join(self.current_path, self.folder_name)
        self.ALLOWED_EXTENSIONS = {'tif', 'tiff'}

        # Set app configuration
        self.app.config['UPLOAD_FOLDER'] = self.UPLOAD_FOLDER
        self.app.config['OUTPUT_FOLDER'] = self.OUTPUT_FOLDER
        self.app.config['DISPLAY_FOLDER'] = self.DISPLAY_FOLDER
        self.app.config['TILES_FOLDER'] = self.TILES_FOLDER

        # Define settings for Detectree2
        self.settings = {
            "main": {
                "site_path": self.OUTPUT_FOLDER,
                "tiles_path": self.TILES_FOLDER
            },
            "tiling": {
                "buffer": 30,
                "tile_width": 40,
                "tile_height": 40
            },
            "crown": {
                "confidence": 0.6
            }
        }

        # Initialize various processors and analysis tools
        self.geoidentifier = GeoImageProcessor()
        self.dt2 = Detectree2(settings=self.settings)
        self.s2Downloader = Sentinel2Downloader()
        self.tifpngconverter = TifImageConverter(output_directory=self.DISPLAY_FOLDER)
        self.ndvianalyzer = NDVIAnalyzer(output_dir=self.OUTPUT_FOLDER)

        # Set up routes
        self._setup_routes()

    def _setup_routes(self):
        @self.app.route('/')
        def index():
            """
            Renders the index page with the current settings.

            Returns:
                str: Rendered HTML page.
            """
            self.logger.info("Rendering index page.")
            return render_template('index.html', settings=self.settings)

        @self.app.route('/upload', methods=['POST'])
        def upload_file():
            """
            Handles file uploads and returns file paths.

            Returns:
                json: JSON response with file paths.
            """
            self.logger.info("Handling file upload.")
            try:
                self._clean_folder_structure()
                
                if 'file' not in request.files or 'input_date' not in request.form:
                    self.logger.warning("File or input date missing in the request.")
                    return jsonify({"status": "error", "message": "File or input date missing in the request."}), 400
                
                file = request.files['file']
                input_date_str = request.form['input_date']
                
                if file.filename == '':
                    self.logger.warning("No file selected for uploading.")
                    return jsonify({"status": "error", "message": "No file selected for uploading."}), 400
                
                if file and self._allowed_file(file.filename):
                    # Parse the input date
                    try:
                        input_date = datetime.strptime(input_date_str, '%Y-%m-%d')
                    except ValueError:
                        self.logger.warning("Invalid input date format.")
                        return jsonify({"status": "error", "message": "Invalid input date format. Expected YYYY-MM-DD."}), 400
                    
                    # Calculate start and end dates (one month before and after the input date)
                    start_date = (input_date - timedelta(days=30)).strftime('%Y-%m-%d')
                    end_date = (input_date + timedelta(days=30)).strftime('%Y-%m-%d')
                    
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(self.app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    self.logger.info(f"File uploaded and saved to {file_path}.")
                    crs = self._get_image_crs(file_path)
                    
                    picture_corner_lat_lng = self.geoidentifier.process_image(file_path)
                    nvdi_path = self.s2Downloader.download_nvdi_image(
                        picture_corner_lat_lng[0][1], 
                        picture_corner_lat_lng[0][0],
                        picture_corner_lat_lng[2][1],
                        picture_corner_lat_lng[2][0],
                        start_date,
                        end_date,
                        crs
                    )
                    self.logger.info(f"NDVI image downloaded to {nvdi_path}.")
                    
                    display_path = self.tifpngconverter.convert(file_path)
                    self.logger.info(f"Image converted for display at {display_path}.")
                    
                    return jsonify({'filepath': file_path, 'displaypath': str(display_path)})
                else:
                    self.logger.warning("Invalid file format.")
                    return jsonify({"status": "error", "message": "Invalid file format."}), 400
            
            except Exception as e:
                self.logger.error(f"Error during file upload: {str(e)}")
                return jsonify({"status": "error", "message": str(e)}), 500


        @self.app.route('/evaluate', methods=['POST'])
        def evaluate_image():
            """
            Evaluates the uploaded image using the Detectree2 model.

            Returns:
                json: JSON response with paths to input and output images.
            """
            self.logger.info("Evaluating image with Detectree2.")
            try:
                data = request.json
                image_path = Path(data['image_path'])
                model_path = Path(data['model_path'])
                
                if os.path.exists(self.TILES_FOLDER):
                    shutil.rmtree(self.TILES_FOLDER)
                os.makedirs(self.TILES_FOLDER, exist_ok=True)
                
                image_path = self.tifpngconverter.convert_to_uint8(image_path)
                output_img = self.dt2.evaluate_image(image_path, model_path)
                
                output_img_path = os.path.join(self.app.config['OUTPUT_FOLDER'], 'output.png')
                output_img.save(output_img_path)
                self.logger.info(f"Image evaluation complete, output saved to {output_img_path}.")
                
                ndvi_stats = self.ndvianalyzer.calculate(self.OUTPUT_FOLDER + "crowns_out.gpkg", self.UPLOAD_FOLDER + "ndvi.tif")
                ndvi_masked_path = os.path.join(self.OUTPUT_FOLDER, "masked_ndvi.png")
                self.logger.info("NDVI statistics calculated and image plotted.")
                
                return jsonify({'input_image': str(image_path), 'output_image': output_img_path, 'ndvi_stats': ndvi_stats, 'ndvi_image': ndvi_masked_path})
            
            except Exception as e:
                self.logger.error(f"Error during image evaluation: {str(e)}")
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/calculate-tiles', methods=['POST'])
        def transform_bounds():
            """
            Calculates the number of tiles based on the image path.

            Returns:
                json: JSON response with the calculated number of tiles.
            """
            self.logger.info("Calculating tiles.")
            try:
                json_data = request.get_json()
                file_path = json_data['file']

                data = rasterio.open(file_path)
                tile_width = int(self.settings["tiling"]["tile_width"])
                tile_height = int(self.settings["tiling"]["tile_height"])
                
                total_tiles = int(
                    ((data.bounds[2] - data.bounds[0]) / tile_width) * ((data.bounds[3] - data.bounds[1]) / tile_height))
                
                self.logger.info(f"Total tiles calculated: {total_tiles}")
                return jsonify({'total_tiles': total_tiles})
            
            except Exception as e:
                self.logger.error(f"Error during tile calculation: {str(e)}")
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/download_image', methods=['POST'])
        def download_image():
            """
            Downloads an image based on the specified coordinates.

            Returns:
                json: JSON response with file paths to the downloaded and displayed images.
            """
            self.logger.info("Downloading image based on coordinates.")
            try:
                self._clean_folder_structure()
                data = request.json
                start_date = data.get('start_date', '2022-01-01')
                end_date = data.get('end_date', '2023-01-31')
                coordinates = data['coordinates']
                file_paths = self.s2Downloader.download_rgb_nvdi_image(
                    coordinates[0][1], 
                    coordinates[0][0],
                    coordinates[2][1],
                    coordinates[2][0],
                    start_date,
                    end_date
                )
                display_path = self.tifpngconverter.convert(file_paths[0])
                self.logger.info(f"Image downloaded and converted for display at {display_path}.")
                
                return jsonify({'filepath': file_paths[0], 'displaypath': display_path})
            
            except Exception as e:
                self.logger.error(f"Error during image download: {str(e)}")
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/uploads/<filename>')
        def uploaded_file(filename):
            """
            Serves the uploaded file.

            Returns:
                Response: File response from the upload directory.
            """
            self.logger.info(f"Serving uploaded file: {filename}")
            return send_from_directory(self.app.config['UPLOAD_FOLDER'], filename)

        @self.app.route('/outputs/<filename>')
        def output_file(filename):
            """
            Serves the output file.

            Returns:
                Response: File response from the output directory.
            """
            self.logger.info(f"Serving output file: {filename}")
            return send_from_directory(self.app.config['OUTPUT_FOLDER'], filename)

        @self.app.route('/display/<filename>')
        def display_file(filename):
            """
            Serves the image file from the display directory.

            Returns:
                Response: File response from the display directory.
            """
            self.logger.info(f"Serving display file: {filename}")
            return send_from_directory(self.app.config['DISPLAY_FOLDER'], filename)

        @self.app.route('/save_settings', methods=['POST'])
        def save_settings():
            """
            Saves and updates the settings for the Detectree2 model.

            Returns:
                json: JSON response confirming success.
            """
            self.logger.info("Saving new settings.")
            try:
                new_settings = request.json
                self.settings['tiling'].update(new_settings.get('tiling', {}))
                self.settings['crown'].update(new_settings.get('crown', {}))
                
                self.dt2.settings = self.settings
                self.logger.info("Settings updated successfully.")

                return jsonify({'status': 'success'})
            
            except Exception as e:
                self.logger.error(f"Error during settings update: {str(e)}")
                return jsonify({"status": "error", "message": str(e)}), 500
            
    def _get_image_crs(self, file_path):
        """
        Retrieves the Coordinate Reference System (CRS) of the image.

        Args:
            file_path (str): Path to the image file.

        Returns:
            str: CRS of the image.
        """
        with rasterio.open(file_path) as dataset:
            return dataset.crs.to_string()

    def _clean_folder_structure(self):
        """
        Cleans and recreates the folder structure for uploads, outputs, display, and tiles.
        """
        self.logger.info("Cleaning folder structure.")
        if os.path.exists(self.UPLOAD_FOLDER):
            shutil.rmtree(self.UPLOAD_FOLDER)
        if os.path.exists(self.OUTPUT_FOLDER):
            shutil.rmtree(self.OUTPUT_FOLDER)
        if os.path.exists(self.DISPLAY_FOLDER):
            shutil.rmtree(self.DISPLAY_FOLDER)
        if os.path.exists(self.TILES_FOLDER):
            shutil.rmtree(self.TILES_FOLDER)
        os.makedirs(self.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(self.OUTPUT_FOLDER, exist_ok=True)
        os.makedirs(self.DISPLAY_FOLDER, exist_ok=True)
        os.makedirs(self.TILES_FOLDER, exist_ok=True)

    def _allowed_file(self, filename):
        """
        Checks if the uploaded file has an allowed extension.

        Args:
            filename (str): The name of the file to check.

        Returns:
            bool: True if the file has an allowed extension, otherwise False.
        """
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.ALLOWED_EXTENSIONS

    def run(self):
        """
        Starts the Flask application.
        """
        self.logger.info("Starting the Flask application.")
        self._clean_folder_structure()
        self.app.run()

if __name__ == '__main__':
    app = FlaskAppWrapper()
    app.run()
