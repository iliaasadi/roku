from flask import Flask, send_from_directory, jsonify, request
from models import db, Category, MenuItem, WallpaperSettings
from config import SQLALCHEMY_DATABASE_URI, SECRET_KEY
import os
from datetime import datetime
from PIL import Image
import io
import base64

app = Flask(__name__, static_folder='.')
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
db.init_app(app)

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

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

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
    
    # Compress image if provided
    if 'image_url' in data and data['image_url']:
        data['image_url'] = compress_image(data['image_url'])
    
    item = MenuItem(
        name=data['name'],
        description=data['description'],
        price=data['price'],
        image_url=data.get('image_url'),
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
        item.image_url = compress_image(data['image_url'])
    if 'category_id' in data:
        item.category_id = data['category_id']
    
    db.session.commit()
    return jsonify(item.to_dict())

@app.route('/api/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
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
    
    # Compress background image
    compressed_image = compress_image(data['background_image'])
    
    wallpaper = WallpaperSettings.query.first()
    if not wallpaper:
        wallpaper = WallpaperSettings(background_image=compressed_image)
        db.session.add(wallpaper)
    else:
        wallpaper.background_image = compressed_image
    
    db.session.commit()
    return jsonify(wallpaper.to_dict())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True) 