import os
import zipfile
import datetime

def create_backup():
    # Get current timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"Inventro_Backup_{timestamp}.zip"
    
    # Files/Dirs to ignore
    IGNORE_PATTERNS = [
        '.git', '__pycache__', 'venv', 'env', '.vscode', 
        '.DS_Store', 'Inventro_Backup', '.vercel', 'brain'
    ]
    IGNORE_EXTENSIONS = ['.pyc', '.pyo', '.pyd', '.zip']

    print(f"Creating backup: {backup_filename}...")
    
    try:
        with zipfile.ZipFile(backup_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk('.'):
                # Filter directories
                dirs[:] = [d for d in dirs if d not in IGNORE_PATTERNS]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    # Check ignores
                    if any(part in file_path for part in IGNORE_PATTERNS):
                        continue
                    if any(file.endswith(ext) for ext in IGNORE_EXTENSIONS):
                        continue
                        
                    # Add to zip
                    arcname = os.path.relpath(file_path, '.')
                    print(f"  Adding: {arcname}")
                    zipf.write(file_path, arcname)
                    
        print(f"\n✅ Backup created successfully: {os.path.abspath(backup_filename)}")
        
    except Exception as e:
        print(f"\n❌ Error creating backup: {e}")

if __name__ == "__main__":
    create_backup()
