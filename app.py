from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
from flask_socketio import SocketIO, emit
from pathlib import Path
from werkzeug.utils import secure_filename
import os
import numpy as np
import shutil
from PIL import Image, ImageCms

from detectree2_wrapper import Detectree2
from coordinate_identifier import GeoImageProcessor
from sentinal2downloader import Sentinel2Downloader
from image_converter import TifImageConverter
from ndvi_statistics_extractor import NDVIAnalyzer
from logger_config import LoggerConfig


class FlaskAppWrapper:
    def __init__(self):
        """
        Initialisiert die Flask-Anwendung und alle erforderlichen Komponenten.
        """
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app)
        self.logger = LoggerConfig.get_logger(self.__class__.__name__)

        # Definiere Ordnerpfade und erlaubte Dateierweiterungen
        self.UPLOAD_FOLDER = 'uploads/'
        self.OUTPUT_FOLDER = 'outputs/'
        self.DISPLAY_FOLDER = 'display/'
        self.current_path = os.path.abspath(os.getcwd())
        self.folder_name = 'tilespred/'
        self.TILES_FOLDER = os.path.join(self.current_path, self.folder_name)
        self.ALLOWED_EXTENSIONS = {'tif', 'tiff'}

        # Setze App-Konfiguration
        self.app.config['UPLOAD_FOLDER'] = self.UPLOAD_FOLDER
        self.app.config['OUTPUT_FOLDER'] = self.OUTPUT_FOLDER
        self.app.config['DISPLAY_FOLDER'] = self.DISPLAY_FOLDER
        self.app.config['TILES_FOLDER'] = self.TILES_FOLDER

        # Definiere Einstellungen für Detectree2
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

        # Initialisiere verschiedene Prozessoren und Analysewerkzeuge
        self.geoidentifier = GeoImageProcessor()
        self.dt2 = Detectree2(settings=self.settings)
        self.s2Downloader = Sentinel2Downloader()
        self.tifpngconverter = TifImageConverter(output_directory=self.DISPLAY_FOLDER)
        self.ndvianalyzer = NDVIAnalyzer()

        # Route-Definitionen
        self._setup_routes()

    def _setup_routes(self):
        @self.app.route('/')
        def index():
            """
            Rendert die Index-Seite mit den aktuellen Einstellungen.

            Returns:
                str: Gerenderte HTML-Seite.
            """
            self.logger.info("Rendering index page.")
            return render_template('index.html', settings=self.settings)

        @self.app.route('/upload', methods=['POST'])
        def upload_file():
            """
            Verarbeitet Datei-Uploads und gibt die Dateipfade zurück.

            Returns:
                json: JSON-Antwort mit Dateipfaden.
            """
            self.logger.info("Handling file upload.")
            self.clean_folder_structure()
            
            if 'file' not in request.files:
                self.logger.warning("No file part in the request.")
                return redirect(request.url)
            file = request.files['file']
            if file.filename == '':
                self.logger.warning("No file selected for uploading.")
                return redirect(request.url)
            if file and self.allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(self.app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                self.logger.info(f"File uploaded and saved to {file_path}.")
                
                picture_corner_lat_lng = self.geoidentifier.process_image(file_path)
                nvdi_path = self.s2Downloader.download_nvdi_image(
                    picture_corner_lat_lng[0][1], 
                    picture_corner_lat_lng[0][0],
                    picture_corner_lat_lng[2][1],
                    picture_corner_lat_lng[2][0],
                    '2022-01-01',
                    '2023-01-31'
                )
                self.logger.info(f"NDVI image downloaded to {nvdi_path}.")
                
                display_path = self.tifpngconverter.convert(file_path)
                self.logger.info(f"Image converted for display at {display_path}.")
                return jsonify({'filepath': file_path, 'displaypath': str(display_path)})

        @self.app.route('/evaluate', methods=['POST'])
        def evaluate_image():
            """
            Bewertet das hochgeladene Bild mit dem Detectree2-Modell.

            Returns:
                json: JSON-Antwort mit Pfaden zu den Eingabe- und Ausgabebildern.
            """
            self.logger.info("Evaluating image with Detectree2.")
            data = request.json
            image_path = Path(data['image_path'])
            model_path = Path(data['model_path'])
            
            image_path = self.tifpngconverter.convert_to_uint8(image_path)
            output_img = self.dt2.evaluate_image(image_path, model_path)
            output_img_path = os.path.join(self.app.config['OUTPUT_FOLDER'], 'output.png')
            output_img.save(output_img_path)
            self.logger.info(f"Image evaluation complete, output saved to {output_img_path}.")
            
            ndvi_stats = self.ndvianalyzer.calculate(self.OUTPUT_FOLDER + "crowns_out.gpkg", self.UPLOAD_FOLDER + "ndvi.tif")
            self.logger.info("NDVI statistics calculated.")
            
            return jsonify({'input_image': str(image_path), 'output_image': output_img_path})

        @self.app.route('/uploads/<filename>')
        def uploaded_file(filename):
            """
            Dient die hochgeladene Datei.

            Returns:
                Response: Datei-Antwort aus dem Upload-Ordner.
            """
            self.logger.info(f"Serving uploaded file: {filename}")
            return send_from_directory(self.app.config['UPLOAD_FOLDER'], filename)

        @self.app.route('/outputs/<filename>')
        def output_file(filename):
            """
            Dient die Ausgabedatei.

            Returns:
                Response: Datei-Antwort aus dem Ausgabeverzeichnis.
            """
            self.logger.info(f"Serving output file: {filename}")
            return send_from_directory(self.app.config['OUTPUT_FOLDER'], filename)

        @self.app.route('/display/<filename>')
        def display_file(filename):
            """
            Dient die Bilddatei im Anzeige-Ordner.

            Returns:
                Response: Datei-Antwort aus dem Anzeige-Ordner.
            """
            self.logger.info(f"Serving display file: {filename}")
            return send_from_directory(self.app.config['DISPLAY_FOLDER'], filename)

        @self.app.route('/save_settings', methods=['POST'])
        def save_settings():
            """
            Speichert und aktualisiert die Einstellungen für das Detectree2-Modell.

            Returns:
                json: JSON-Antwort, die den Erfolg bestätigt.
            """
            self.logger.info("Saving new settings.")
            new_settings = request.json
            self.settings['tiling'].update(new_settings.get('tiling', {}))
            self.settings['crown'].update(new_settings.get('crown', {}))
            
            self.dt2.settings = self.settings
            self.logger.info("Settings updated successfully.")

            return jsonify({'status': 'success'})

        @self.app.route('/download_image', methods=['POST'])
        def download_image():
            """
            Lädt ein Bild basierend auf den angegebenen Koordinaten herunter.

            Returns:
                json: JSON-Antwort mit Dateipfaden zu den heruntergeladenen und angezeigten Bildern.
            """
            self.logger.info("Downloading image based on coordinates.")
            self.clean_folder_structure()
            data = request.json
            coordinates = data['coordinates']
            file_paths = self.s2Downloader.download_rgb_nvdi_image(
                coordinates[0][1], 
                coordinates[0][0],
                coordinates[2][1],
                coordinates[2][0],
                '2022-01-01',
                '2023-01-31'
            )
            display_path = self.tifpngconverter.convert(file_paths[0])
            self.logger.info(f"Image downloaded and converted for display at {display_path}.")
            
            return jsonify({'filepath': file_paths[0], 'displaypath': display_path})

    def clean_folder_structure(self):
        """
        Reinigt und erstellt die Ordnerstruktur für Uploads, Ausgaben, Anzeigen und Tiles neu.
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

    def allowed_file(self, filename):
        """
        Prüft, ob die hochgeladene Datei eine zulässige Erweiterung hat.

        Args:
            filename (str): Der Name der Datei, die überprüft werden soll.

        Returns:
            bool: True, wenn die Datei eine zulässige Erweiterung hat, sonst False.
        """
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.ALLOWED_EXTENSIONS

    def run(self):
        """
        Startet die Flask-Anwendung.
        """
        self.logger.info("Starting the Flask application.")
        self.clean_folder_structure()
        self.socketio.run(self.app, debug=True)

if __name__ == '__main__':
    app = FlaskAppWrapper()
    app.run()
