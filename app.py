import os
import json
import time
import shutil
import zipfile
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route("/")
def index():
    return render_template('index.html')
@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    """Handle file upload and return the column names."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)

    # Extract column names based on file type
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(file_path)
            columns = df.columns.tolist()
        elif filename.endswith('.json'):
            with open(file_path) as f:
                json_data = json.load(f)
            if isinstance(json_data, list) and len(json_data) > 0 and isinstance(json_data[0], dict):
                columns = list(json_data[0].keys())
            else:
                return jsonify({'error': 'Invalid JSON format'}), 400
        else:
            return jsonify({'error': 'Unsupported file type'}), 400
    except Exception as e:
        return jsonify({'error': f'Failed to read file: {str(e)}'}), 400

    return jsonify({'columns': columns, 'fileName': filename})


@app.route('/generate_manifest', methods=['POST'])
def generate_manifest():
    """Generate the manifest, modify the file, and zip both files."""
    data = request.json
    client_email = data.get('clientEmail', 'unknown_client')
    columns = data['columns']
    timestamp = int(time.time())
    file_name = data["fileName"]
    original_file_path = os.path.join(UPLOAD_FOLDER, file_name)

    # Determine type-specific prefixes
    if data["type"] == "event":
        event_name = data.get('event_name', 'default_event')
        folder_name = f"event_{event_name}_{timestamp}"
        csv_file_prefix = f"event_{event_name}_{timestamp}"
    else:
        folder_name = f"profile_{timestamp}"
        csv_file_prefix = f"profile_{timestamp}"

    folder_path = os.path.join(OUTPUT_FOLDER, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    # Generate the manifest file
    manifest = {
        "fileName": f"{csv_file_prefix}.csv",
        "type": data["type"],
        "columns": {col['csv_name']: {
                        'ctName': col['clevertap_name'],
                        'dataType': col['type'].upper()
                    } for col in columns},
        "clientEmail": client_email
    }

    manifest_path = os.path.join(folder_path, 'manifest.json')
    with open(manifest_path, 'w') as manifest_file:
        json.dump(manifest, manifest_file, indent=4)

    try:
        # Modify the data file
        if file_name.endswith('.csv'):
            df = pd.read_csv(original_file_path)
        elif file_name.endswith('.json'):
            with open(original_file_path) as f:
                json_data = json.load(f)
            df = pd.json_normalize(json_data)
        else:
            return jsonify({'error': 'Unsupported file type'}), 400

        # Save the modified CSV
        modified_csv_filename = f"{csv_file_prefix}.csv"
        modified_csv_path = os.path.join(folder_path, modified_csv_filename)
        df.to_csv(modified_csv_path, index=False)

        # Create a zip file
        zip_path = os.path.join(OUTPUT_FOLDER, f"{folder_name}.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            zipf.write(manifest_path, arcname=os.path.join(folder_name, 'manifest.json'))
            zipf.write(modified_csv_path, arcname=os.path.join(folder_name, modified_csv_filename))

        return jsonify({
            'manifest_url': f"/download/{folder_name}/manifest.json",
            'csv_url': f"/download/{folder_name}/{modified_csv_filename}",
            'zip_url': f"/download/{folder_name}.zip"
        })

    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 400


@app.route('/download/<path:filename>', methods=['GET'])
def download_file(filename):
    """Download files (manifest, CSV, or zip)."""
    file_path = os.path.join(OUTPUT_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)
