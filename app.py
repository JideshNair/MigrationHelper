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
    """Handle CSV file upload and return the column names."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)

    # Extract column names from the CSV
    try:
        df = pd.read_csv(file_path)
        columns = df.columns.tolist()
    except Exception as e:
        return jsonify({'error': f'Failed to read CSV: {str(e)}'}), 400

    return jsonify({'columns': columns, 'fileName': filename})

@app.route('/generate_manifest', methods=['POST'])
def generate_manifest():
    """Generate the manifest, modify the CSV, and zip both files."""
    data = request.json
    client_email = data.get('clientEmail', 'unknown_client')
    columns = data['columns']
    timestamp = int(time.time())  # Use the current epoch time as timestamp
    file_name = data["fileName"]
    original_file_path = os.path.join(UPLOAD_FOLDER, file_name)

    # Determine type-specific prefixes
    if data["type"] == "event":
        event_name = data.get('event_name', 'default_event')
        folder_name = f"event_{event_name}_{timestamp}"
        csv_file_prefix = f"event_{event_name}_{timestamp}"
    else:  # Profile
        folder_name = f"profile_{timestamp}"
        csv_file_prefix = f"profile_{timestamp}"

    # Create folder for this event/profile
    folder_path = os.path.join(OUTPUT_FOLDER, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    # Generate the manifest file in the desired format
    manifest = {
        "fileName": f"{csv_file_prefix}.csv",  # CSV filename will use the prefix
        "type": data["type"],
        "columns": {col['csv_name']: {
                        'clevertap_name': col['clevertap_name'],
                        'data_type': col['type'].lower()
                    } for col in columns},
        "clientEmail": client_email
    }

    manifest_path = os.path.join(folder_path, 'manifest.json')
    with open(manifest_path, 'w') as manifest_file:
        json.dump(manifest, manifest_file, indent=4)

    # Modify the CSV file
    try:
        df = pd.read_csv(original_file_path)
    except Exception as e:
        return jsonify({'error': f'Failed to read CSV: {str(e)}'}), 400

    # Add 'event_name' column if it's event type
    if data["type"] == "event" and 'event_name' not in df.columns:
        df['event_name'] = event_name

    # Map column names based on user inputs
    column_mapping = {col['csv_name']: col['clevertap_name'] for col in columns}
    df.rename(columns=column_mapping, inplace=True)

    # Add the event name to the selected event column
    if data["type"] == "event" and event_name in df.columns:
        df['event_name'] = df[event_name]  # Event column is selected by the user

    # Save the modified CSV with the new filename
    modified_csv_filename = f"{csv_file_prefix}.csv"
    modified_csv_path = os.path.join(folder_path, modified_csv_filename)
    df.to_csv(modified_csv_path, index=False)

    # Create a zip file containing the manifest and modified CSV
    zip_path = os.path.join(OUTPUT_FOLDER, f"{folder_name}.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        zipf.write(manifest_path, arcname=os.path.join(folder_name, 'manifest.json'))
        zipf.write(modified_csv_path, arcname=os.path.join(folder_name, modified_csv_filename))

    return jsonify({
        'manifest_url': f"/download/{folder_name}/manifest.json",
        'csv_url': f"/download/{folder_name}/{modified_csv_filename}",
        'zip_url': f"/download/{folder_name}.zip"
    })

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
