from flask import Flask, send_from_directory, jsonify, request
from models import db, Category, MenuItem, WallpaperSettings
from config import SQLALCHEMY_DATABASE_URI, SECRET_KEY
import os
from datetime import datetime
from PIL import Image
import io
import base64
import uuid
import shutil

app = Flask(__name__, static_folder='.')
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
db.init_app(app)

def get_default_image_path() -> str:
    """Ensure a default image exists in static/uploads and return its relative path."""
    uploads_dir = os.path.join('static', 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    default_rel = os.path.join('static', 'uploads', 'default_logo.jpg')
    default_abs = os.path.join(uploads_dir, 'default_logo.jpg')
    source_logo = 'logo.jpg'

    try:
        if not os.path.exists(default_abs):
            with Image.open(source_logo) as img:
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                else:
                    img = img.convert('RGB')
                img.save(default_abs, format='JPEG', quality=85, optimize=True)
    except Exception:
        # If anything goes wrong, fall back to original logo path being served from root
        return source_logo

    return default_rel

def save_image_to_file(image_data, upload_folder='static/uploads'):
    """Save base64 image data to file and return the file path"""
    try:
        # Ensure upload directory exists
        os.makedirs(upload_folder, exist_ok=True)
        
        # Convert base64 to image
        if isinstance(image_data, str) and image_data.startswith('data:image'):
            # Remove data URL prefix
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Generate unique filename
        filename = f"{uuid.uuid4()}.jpg"
        file_path = os.path.join(upload_folder, filename)
        
        # Compress and save image
        quality = 85
        img.save(file_path, format='JPEG', quality=quality, optimize=True)
        
        # Return relative path for database storage
        return f"static/uploads/{filename}"
    except Exception as e:
        print(f"Error saving image: {e}")
        # Return None or a default image path if there's an error
        return None

def compress_image(image_data, max_size_kb=50):
    """Compress image to specified size in KB while maintaining quality"""
    # Convert base64 to image
    if isinstance(image_data, str) and image_data.startswith('data:image'):
        # Remove data URL prefix
        image_data = image_data.split(',')[1]
    
    image_bytes = base64.b64decode(image_data)
    img = Image.open(io.BytesIO(image_bytes))
    
    # Convert to RGB if necessary
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    # Calculate initial quality
    quality = 95
    output = io.BytesIO()
    
    # Compress image with reducing quality until size is under max_size_kb
    while True:
        output.seek(0)
        output.truncate()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        size_kb = len(output.getvalue()) / 1024
        
        if size_kb <= max_size_kb or quality <= 5:
            break
            
        quality -= 5
    
    # Convert back to base64
    compressed_base64 = base64.b64encode(output.getvalue()).decode('utf-8')
    return f"data:image/jpeg;base64,{compressed_base64}"

# Create database tables
with app.app_context():
    db.create_all()
    # Create default wallpaper settings if not exists
    if not WallpaperSettings.query.first():
        default_wallpaper = WallpaperSettings(background_image='')
        db.session.add(default_wallpaper)
        db.session.commit()

    # Backfill: ensure items without images get the default image
    try:
        default_path = get_default_image_path()
        # Update rows where image_url is NULL or empty
        MenuItem.query.filter((MenuItem.image_url.is_(None)) | (MenuItem.image_url == '')).update({MenuItem.image_url: default_path})
        db.session.commit()
    except Exception:
        db.session.rollback()

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/static/<path:filename>')
def serve_static_files(filename):
    """Serve static files from the static directory"""
    return send_from_directory('static', filename)

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

# API Routes
@app.route('/api/categories', methods=['GET'])
def get_categories():
    categories = Category.query.all()
    return jsonify([category.to_dict() for category in categories])

@app.route('/api/categories', methods=['POST'])
def create_category():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'Category name is required'}), 400
    
    category = Category(name=data['name'])
    db.session.add(category)
    db.session.commit()
    return jsonify(category.to_dict()), 201

@app.route('/api/categories/<int:category_id>', methods=['GET', 'PUT', 'DELETE'])
def category(category_id):
    try:
        if request.method == 'GET':
            category = Category.query.get(category_id)
            if not category:
                return jsonify({'error': 'Category not found'}), 404
            return jsonify({
                'id': category.id,
                'name': category.name
            })
        elif request.method == 'PUT':
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
                
            category = Category.query.get(category_id)
            if not category:
                return jsonify({'error': 'Category not found'}), 404
                
            if 'name' in data:
                category.name = data['name']
                try:
                    db.session.commit()
                    return jsonify({
                        'id': category.id,
                        'name': category.name
                    })
                except Exception as e:
                    db.session.rollback()
                    return jsonify({'error': str(e)}), 500
            return jsonify({'error': 'No valid data provided'}), 400
        elif request.method == 'DELETE':
            category = Category.query.get(category_id)
            if not category:
                return jsonify({'error': 'Category not found'}), 404
            try:
                # Delete all items in this category first
                MenuItem.query.filter_by(category_id=category_id).delete()
                db.session.delete(category)
                db.session.commit()
                return jsonify({'message': 'Category deleted successfully'})
            except Exception as e:
                db.session.rollback()
                return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/items', methods=['GET'])
def get_items():
    items = MenuItem.query.all()
    return jsonify([item.to_dict() for item in items])

@app.route('/api/items', methods=['POST'])
def create_item():
    data = request.get_json()
    if not data or not all(k in data for k in ['name', 'description', 'price', 'category_id']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Save image to file if provided
    image_path = None
    if 'image_url' in data and data['image_url']:
        image_path = save_image_to_file(data['image_url'])
    if not image_path:
        image_path = get_default_image_path()
    
    item = MenuItem(
        name=data['name'],
        description=data['description'],
        price=data['price'],
        image_url=image_path,
        category_id=data['category_id']
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201

@app.route('/api/items/<int:item_id>', methods=['GET'])
def get_item(item_id):
    item = MenuItem.query.get(item_id)
    if not item:
        return jsonify({'error': 'Item not found'}), 404
    return jsonify(item.to_dict())

@app.route('/api/items/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    data = request.get_json()
    
    if 'name' in data:
        item.name = data['name']
    if 'description' in data:
        item.description = data['description']
    if 'price' in data:
        item.price = data['price']
    if 'image_url' in data and data['image_url']:
        # Delete old image file if it exists
        if item.image_url and os.path.exists(item.image_url):
            try:
                os.remove(item.image_url)
            except OSError:
                pass  # File might not exist or be accessible
        
        # Save new image
        item.image_url = save_image_to_file(data['image_url'])
    if 'category_id' in data:
        item.category_id = data['category_id']
    
    db.session.commit()
    return jsonify(item.to_dict())

@app.route('/api/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    
    # Delete associated image file if it exists
    if item.image_url and os.path.exists(item.image_url):
        try:
            os.remove(item.image_url)
        except OSError:
            pass  # File might not exist or be accessible
    
    db.session.delete(item)
    db.session.commit()
    return '', 204

@app.route('/api/wallpaper', methods=['GET'])
def get_wallpaper():
    wallpaper = WallpaperSettings.query.first()
    if not wallpaper:
        wallpaper = WallpaperSettings(background_image='')
        db.session.add(wallpaper)
        db.session.commit()
    return jsonify(wallpaper.to_dict())

@app.route('/api/wallpaper', methods=['PUT'])
def update_wallpaper():
    data = request.get_json()
    if not data or 'background_image' not in data:
        return jsonify({'error': 'Background image URL is required'}), 400
    
    # Save background image to file
    image_path = save_image_to_file(data['background_image'])
    
    wallpaper = WallpaperSettings.query.first()
    if not wallpaper:
        wallpaper = WallpaperSettings(background_image=image_path)
        db.session.add(wallpaper)
    else:
        # Delete old wallpaper file if it exists
        if wallpaper.background_image and os.path.exists(wallpaper.background_image):
            try:
                os.remove(wallpaper.background_image)
            except OSError:
                pass  # File might not exist or be accessible
        
        wallpaper.background_image = image_path
    
    db.session.commit()
    return jsonify(wallpaper.to_dict())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True) 