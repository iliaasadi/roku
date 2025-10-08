from flask import Flask
from models import db, MenuItem, WallpaperSettings
from config import SQLALCHEMY_DATABASE_URI

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def reset_images():
    with app.app_context():
        # Reset all menu item images
        MenuItem.query.update({MenuItem.image_url: ''})
        
        # Reset wallpaper image
        wallpaper = WallpaperSettings.query.first()
        if wallpaper:
            wallpaper.background_image = ''
        
        # Commit changes
        db.session.commit()
        print("All images have been reset successfully!")

if __name__ == '__main__':
    reset_images() 