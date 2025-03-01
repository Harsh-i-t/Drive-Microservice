from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io, os, base64, json
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)

# Google Drive credentials
# SERVICE_ACCOUNT_FILE = "service_account.json"
SCOPES = ['https://www.googleapis.com/auth/drive']
PARENT_FOLDER_ID = os.getenv("PARENT_FOLDER_ID")
SECOND_PARENT_FOLDER_ID = os.getenv("SECOND_PARENT_FOLDER_ID")

def authenticate():
    """Authenticate and initialize the Google Drive service."""
    try:
        # Decode the base64-encoded key
        encoded_key = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")
        if not encoded_key:
            raise ValueError("Google Service Account Key is missing.")

        service_account_info = json.loads(base64.b64decode(encoded_key))
        creds = service_account.Credentials.from_service_account_info(service_account_info)
        
        service = build("drive", "v3", credentials=creds)
        return service

    except Exception as e:
        print(f"❌ Error initializing Google Drive service: {e}")
        return None

def create_folder(service, parent_id, folder_name):
    """Creates a folder in Google Drive if it doesn't exist and returns its ID."""
    try:
        # Check if the folder exists
        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and '{parent_id}' in parents and trashed=false"
        response = service.files().list(q=query, fields="files(id)").execute()
        folders = response.get("files", [])

        if folders:
            return folders[0]['id']

        # Create the folder
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = service.files().create(body=folder_metadata, fields="id").execute()
        return folder['id']

    except Exception as e:
        print(f"❌ Error creating folder '{folder_name}': {e}")
        return None

@app.route("/api/upload", methods=["POST"])
def upload_ss_drive():
    """API endpoint to upload a file to Google Drive."""
    try:
        # Get request data
        file = request.files.get("file")
        company = request.form.get("company")
        employee_id = request.form.get("employee_id")
        date = request.form.get("date")
        filename = request.form.get("filename")

        if not file or not company or not employee_id or not date:
            return jsonify({"error": "Missing required fields"}), 400

        # Authenticate and initialize service
        service = authenticate()
        if not service:
            return jsonify({"error": "Failed to authenticate with Google Drive"}), 500

        # Ensure the folder structure exists
        company_folder_id = create_folder(service, PARENT_FOLDER_ID, company)
        employee_folder_id = create_folder(service, company_folder_id, employee_id)
        date_folder_id = create_folder(service, employee_folder_id, date)

        # Read file directly from memory
        file_stream = io.BytesIO(file.read())

        # Upload the file to Google Drive
        file_metadata = {
            "name": filename,
            "parents": [date_folder_id]
        }
        media = MediaIoBaseUpload(file_stream, mimetype="image/png", resumable=True)

        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink"
        ).execute()

        # Return the Google Drive file link
        return jsonify({
            "message": "File uploaded successfully",
            "data": uploaded_file.get("webViewLink")
        }), 200

    except Exception as e:
        print(f"❌ Error in upload_to_drive: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/upload_extras", methods=["POST"])
def upload_to_drive():
    """Uploads a file to Google Drive inside a specific folder."""
    try:
        file = request.files.get("file")
        folder_name = request.form.get("folder_name")
        employee_name = request.form.get("employee_name")
        service = authenticate()
        if not service:
            raise Exception("Google Drive authentication failed")

        # Create employee and folder structure
        target_folder_id = create_folder(service, SECOND_PARENT_FOLDER_ID, folder_name)
        employee_folder_id = create_folder(service, target_folder_id, employee_name)

        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{employee_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}{file_extension}"

        # Prepare file metadata
        file_metadata = {
            "name": unique_filename,
            "parents": [employee_folder_id],
        }

        # Upload file
        media = MediaIoBaseUpload(io.BytesIO(file.read()), mimetype=file.content_type)
        uploaded_file = service.files().create(
            body=file_metadata, media_body=media, fields="id, webViewLink"
        ).execute()

        # Return the Google Drive file link
        return jsonify({
            "message": "File uploaded successfully",
            "data": uploaded_file.get("webViewLink")
        }), 200

    except Exception as e:
        raise Exception(f"❌ Error uploading to Google Drive: {e}")
    
# home route
@app.route("/")
def home():
    return jsonify({"message": "Mircroservice is running"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=True)
