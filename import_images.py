#!/usr/bin/env python3
import os
import uuid
import sqlite3
from pathlib import Path
from PIL import Image
import re
import unicodedata

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'menu.db'
TEST_DIR = BASE_DIR / 'static' / 'test'
UPLOADS_DIR = BASE_DIR / 'static' / 'uploads'
DEFAULT_IMAGE = 'logo.jpg'  # used as UI default if no image

SUPPORTED_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.gif'}


def normalize_name(text: str) -> str:
	"""Normalize name for matching: lower, remove diacritics, non-letters to space, collapse spaces."""
	if not text:
		return ''
	# Normalize unicode (e.g., Persian/Arabic letters)
	nfkd_form = unicodedata.normalize('NFKD', text)
	# Remove diacritics
	without_marks = ''.join(ch for ch in nfkd_form if not unicodedata.combining(ch))
	# Lowercase
	lowered = without_marks.lower()
	# Replace separators and punctuation with space
	sanitized = re.sub(r'[^\w\u0600-\u06FF]+', ' ', lowered)
	# Collapse whitespace
	collapsed = re.sub(r'\s+', ' ', sanitized).strip()
	return collapsed


def find_images() -> list[Path]:
	if not TEST_DIR.exists():
		return []
	files = []
	for entry in TEST_DIR.iterdir():
		if entry.is_file() and entry.suffix.lower() in SUPPORTED_EXTS:
			files.append(entry)
	return files


def convert_to_jpeg(src_path: Path) -> str:
	"""Convert any supported image to JPEG, store under static/uploads with UUID name, return relative db path."""
	UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
	with Image.open(src_path) as img:
		# Convert to RGB for JPEG
		if img.mode in ('RGBA', 'P'):
			img = img.convert('RGB')
		else:
			img = img.convert('RGB')
		filename = f"{uuid.uuid4()}.jpg"
		dest_path = UPLOADS_DIR / filename
		img.save(dest_path, format='JPEG', quality=85, optimize=True)
		return f"static/uploads/{filename}"


def load_items(conn) -> list[tuple[int, str, str | None]]:
	cur = conn.cursor()
	cur.execute("SELECT id, name, image_url FROM menu_item")
	return [(row[0], row[1], row[2]) for row in cur.fetchall()]


def build_item_index(items):
	index = {}
	for item_id, name, _ in items:
		norm = normalize_name(name)
		index[norm] = item_id
	return index


def best_match(filename_stem: str, item_index: dict) -> int | None:
	"""Try exact normalized match; fallback to contains or partial token overlap."""
	norm_file = normalize_name(filename_stem)
	if not norm_file:
		return None
	# 1) exact
	if norm_file in item_index:
		return item_index[norm_file]
	# 2) token overlap: choose highest overlap
	file_tokens = set(norm_file.split())
	best = (0, None)
	for norm_name, item_id in item_index.items():
		tokens = set(norm_name.split())
		if not tokens:
			continue
		overlap = len(file_tokens & tokens)
		if overlap > best[0]:
			best = (overlap, item_id)
	# Require at least 1 overlapping token
	return best[1] if best[0] > 0 else None


def main():
	print("Starting image import from static/test ...")
	if not DB_PATH.exists():
		print("[ERROR] Database not found at", DB_PATH)
		return
	images = find_images()
	print(f"Found {len(images)} images in {TEST_DIR}")
	conn = sqlite3.connect(DB_PATH)
	try:
		items = load_items(conn)
		item_index = build_item_index(items)
		print(f"Loaded {len(items)} menu items from database")

		updated = 0
		matched = 0
		unmatched_files = []
		filename_to_item = {}

		# First pass: convert and map images to items
		for img_path in images:
			stem = img_path.stem
			item_id = best_match(stem, item_index)
			try:
				rel_path = convert_to_jpeg(img_path)
			except Exception as e:
				print(f"[ERROR] Failed to convert {img_path.name}: {e}")
				continue
			if item_id is not None:
				filename_to_item[img_path.name] = (item_id, rel_path)
				matched += 1
			else:
				unmatched_files.append(img_path.name)

		# Update DB for matched items
		cur = conn.cursor()
		for _, (item_id, rel_path) in filename_to_item.items():
			cur.execute("UPDATE menu_item SET image_url = ? WHERE id = ?", (rel_path, item_id))
			updated += 1
		conn.commit()

		print(f"Matched {matched} images to items; updated {updated} records")
		if unmatched_files:
			print(f"Unmatched image files ({len(unmatched_files)}):")
			for name in unmatched_files:
				try:
					safe = name.encode('cp1252', errors='replace').decode('cp1252')
				except Exception:
					safe = name.encode('ascii', errors='replace').decode('ascii')
				print(" -", safe)

		# Set default for items still without images (leave null in DB; UI shows default)
		cur.execute("UPDATE menu_item SET image_url = NULL WHERE image_url IS NULL OR image_url = ''")
		conn.commit()
		# Note: frontend uses logo.jpg as default display; DB stays null
		print("Set default (null) for items without images; UI will show logo.jpg")
	finally:
		conn.close()
	print("Done.")

if __name__ == '__main__':
	main()
