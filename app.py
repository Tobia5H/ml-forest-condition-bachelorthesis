# app.py
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

app = Flask(__name__)
socketio = SocketIO(app)

UPLOAD_FOLDER = 'uploads/'
OUTPUT_FOLDER = 'outputs/'
DISPLAY_FOLDER = 'display/'
current_path = os.path.abspath(os.getcwd())
folder_name = 'tilespred/'
TILES_FOLDER = os.path.join(current_path, folder_name) # we need to define the folder this way otherwise detectree2's predict() will get wrong path.
ALLOWED_EXTENSIONS = {'tif', 'tiff'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['DISPLAY_FOLDER'] = DISPLAY_FOLDER
app.config['TILES_FOLDER'] = TILES_FOLDER

settings = {
    "main": {
        "site_path": OUTPUT_FOLDER,
        "tiles_path": TILES_FOLDER
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

geoidentifier = GeoImageProcessor()
dt2 = Detectree2(settings=settings)
s2Downloader = Sentinel2Downloader()
tifpngconverter = TifImageConverter(output_directory=DISPLAY_FOLDER)
ndvianalyzer = NDVIAnalyzer()

def clean_folder_structure():
    if os.path.exists(UPLOAD_FOLDER):
        shutil.rmtree(UPLOAD_FOLDER)
    if os.path.exists(OUTPUT_FOLDER):
        shutil.rmtree(OUTPUT_FOLDER)
    if os.path.exists(DISPLAY_FOLDER):
        shutil.rmtree(DISPLAY_FOLDER)
    if os.path.exists(TILES_FOLDER):
        shutil.rmtree(TILES_FOLDER)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    os.makedirs(DISPLAY_FOLDER, exist_ok=True)
    os.makedirs(TILES_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_to_display_format(tif_path):
    with Image.open(tif_path) as img:
        # Check and convert color space if necessary
        if img.mode == "CMYK":
            img = img.convert("RGB")
        elif img.mode not in ["RGB", "RGBA"]:
            try:
                img = ImageCms.profileToProfile(img, None, 'sRGB.icm', outputMode='RGB')
            except Exception as e:
                # If profile conversion fails, fall back to manual conversion
                img = img.convert("RGB")
        
        img = img.convert("RGBA")
        
        # Normalize the image if necessary
        img_array = np.array(img)
        
        normalized_array = np.interp(img_array, (img_array.min(), img_array.max()), (0, 255))
        img = Image.fromarray(normalized_array.astype('uint8'))

        max_width = 2500
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = int((float(img.height) * float(ratio)))
            img = img.resize((max_width, new_height), Image.LANCZOS)
        
        output_path = os.path.splitext(tif_path)[0] + ".png"
        img.save(output_path)
        return output_path

@app.route('/')
def index():
    return render_template('index.html', settings=settings)

@app.route('/upload', methods=['POST'])
def upload_file():
    clean_folder_structure()
    
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        
        picture_corner_lat_lng = geoidentifier.process_image(file_path)
        nvdi_path = s2Downloader.download_nvdi_image(picture_corner_lat_lng[0][1], 
                                     picture_corner_lat_lng[0][0],
                                     picture_corner_lat_lng[2][1],
                                     picture_corner_lat_lng[2][0],
                                     '2022-01-01',
                                     '2023-01-31',
                                     )
        
        display_path = tifpngconverter.convert(file_path)
        return jsonify({'filepath': file_path, 'displaypath': str(display_path)})

@app.route('/evaluate', methods=['POST'])
def evaluate_image():
    data = request.json
    image_path = Path(data['image_path'])
    model_path = Path(data['model_path'])
    
    image_path = tifpngconverter.convert_to_uint8(image_path)
    output_img = dt2.evaluate_image(image_path, model_path)
    output_img_path = os.path.join(app.config['OUTPUT_FOLDER'], 'output.png')
    output_img.save(output_img_path)
    ndvi_stats = ndvianalyzer.calculate(OUTPUT_FOLDER + "crowns_out.gpkg", UPLOAD_FOLDER + "ndvi.tif")

    return jsonify({'input_image': str(image_path), 'output_image': output_img_path})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/outputs/<filename>')
def output_file(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

@app.route('/display/<filename>')
def display_file(filename):
    return send_from_directory(app.config['DISPLAY_FOLDER'], filename)

@app.route('/save_settings', methods=['POST'])
def save_settings():
    global settings
    new_settings = request.json
    settings['tiling'].update(new_settings.get('tiling', {}))
    settings['crown'].update(new_settings.get('crown', {}))
    
    dt2.settings = settings

    return jsonify({'status': 'success'})

@app.route('/download_image', methods=['POST'])
def download_image():
    clean_folder_structure()
    data = request.json
    coordinates = data['coordinates']
    file_paths = s2Downloader.download_rgb_nvdi_image(coordinates[0][1], 
                                     coordinates[0][0],
                                     coordinates[2][1],
                                     coordinates[2][0],
                                     '2022-01-01',
                                     '2023-01-31',
                                     )
    display_path = tifpngconverter.convert(file_paths[0])
    
    return jsonify({'filepath': file_paths[0], 'displaypath': display_path})

if __name__ == '__main__':
    clean_folder_structure()
    socketio.run(app, debug=True)
