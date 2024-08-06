# app.py
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
from flask_socketio import SocketIO, emit
from pathlib import Path
from werkzeug.utils import secure_filename
import os
import json
import shutil
from PIL import Image
from earth_engine_wrapper import GeoTIFFDownloader
from detectree2_wrapper import Detectree2

app = Flask(__name__)
socketio = SocketIO(app)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
DISPLAY_FOLDER = 'display'
ALLOWED_EXTENSIONS = {'tif', 'tiff', 'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['DISPLAY_FOLDER'] = DISPLAY_FOLDER

settings = {
    "main": {
        "site_path": OUTPUT_FOLDER,
        "tiles_path": "/home/tobias/detectree2/tilespred/"
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

service_account = 'python-script-azure-vm@ee-bachelorthesis-forestml.iam.gserviceaccount.com'
key_path = '/home/tobias/detectree2/ee-bachelorthesis-forestml-9f670651e3e4.json'
downloader = GeoTIFFDownloader(service_account, key_path)

dt2 = Detectree2(settings=settings)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_to_display_format(tif_path):
    with Image.open(tif_path) as img:
        img = img.convert("RGBA")
        
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
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        display_path = convert_to_display_format(file_path)

        return jsonify({'filename': filename, 'filepath': file_path, 'displaypath': str(display_path)})

@app.route('/evaluate', methods=['POST'])
def evaluate_image():
    data = request.json
    image_path = Path(data['image_path'])
    model_path = Path(data['model_path'])
    
    output_img = dt2.evaluate_image(image_path, model_path)
    output_img_path = os.path.join(app.config['OUTPUT_FOLDER'], 'output.png')
    output_img.save(output_img_path)

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
    data = request.json
    coordinates = data['coordinates']
    downloader.set_area_of_interest(coordinates)
    
    image_file = os.path.join(app.config['UPLOAD_FOLDER'], "downloaded_image.tif")
    # geotiff_file = os.path.join(app.config['OUTPUT_FOLDER'], "georeferenced_image.tif")
    
    downloader.download_image(image_file)
    # downloader.create_geotiff(image_file, geotiff_file)
    
    display_path = convert_to_display_format(image_file)
    
    return jsonify({'geotiff_file': image_file, 'displaypath': display_path})

if __name__ == '__main__':
    if os.path.exists(UPLOAD_FOLDER):
        shutil.rmtree(UPLOAD_FOLDER)
    if os.path.exists(OUTPUT_FOLDER):
        shutil.rmtree(OUTPUT_FOLDER)
    if os.path.exists(DISPLAY_FOLDER):
        shutil.rmtree(DISPLAY_FOLDER)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    os.makedirs(DISPLAY_FOLDER, exist_ok=True)
    socketio.run(app, debug=True)
