from flask import Flask, request, jsonify, Response
from celery import Celery
import redis
import psycopg2
import psycopg2.extras
import os
import time
import uuid
import hashlib
from datetime import datetime
from PIL import Image
import logging
from werkzeug.utils import secure_filename
from flask_cors import CORS




app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'foodfast_db'),
    'user': os.getenv('DB_USER', 'foodfast'),
    'password': os.getenv('DB_PASSWORD', 'foodfast123'),
    'port': int(os.getenv('DB_PORT', 5432))
}

app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['PROCESSED_FOLDER'] = '/tmp/processed'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Allowed file extensions and sizes
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_IMAGE_SIZE = (2048, 2048)  # Max dimensions
THUMBNAIL_SIZE = (300, 300)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis connection
try:
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    logger.info("Redis connection successful")
except Exception as e:
    logger.error(f"Redis connection failed: {e}")
    r = None

# Celery configuration
celery = Celery(app.name, broker=REDIS_URL, backend=REDIS_URL)

def get_db_connection():
    """Get database connection with retries"""
    max_retries = 5
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting database connection (attempt {attempt + 1}/{max_retries})")
            logger.info(f"Connection params: host={DB_CONFIG['host']}, port={DB_CONFIG['port']}, db={DB_CONFIG['database']}")
            conn = psycopg2.connect(**DB_CONFIG)
            logger.info(f"Successfully connected to database on attempt {attempt + 1}")
            return conn
        except psycopg2.Error as e:
            logger.error(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    logger.error("All database connection attempts failed")
    return None

# Create upload directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_restaurant(restaurant_id):
    """Validate if restaurant exists"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM restaurants WHERE id = %s", (restaurant_id,))
            result = cur.fetchone()
            conn.close()
            return result is not None
    except Exception as e:
        logger.error(f"Error validating restaurant: {e}")
        if conn:
            conn.close()
        return False

def create_upload_job(restaurant_id, original_filename, unique_filename):
    """Create image upload job in database"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO image_upload_jobs (restaurant_id, filename, status, created_at)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (restaurant_id, unique_filename, 'uploaded', datetime.now()))
            
            job_id = cur.fetchone()[0]
            conn.commit()
            conn.close()
            return job_id
    except Exception as e:
        logger.error(f"Error creating upload job: {e}")
        if conn:
            conn.close()
        return None

def update_job_status(job_id, status, completed_at=None):
    """Update job status in database"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as cur:
            if completed_at:
                cur.execute("""
                    UPDATE image_upload_jobs 
                    SET status = %s, completed_at = %s
                    WHERE id = %s
                """, (status, completed_at, job_id))
            else:
                cur.execute("""
                    UPDATE image_upload_jobs 
                    SET status = %s
                    WHERE id = %s
                """, (status, job_id))
            
            conn.commit()
            conn.close()
            return True
    except Exception as e:
        logger.error(f"Error updating job status: {e}")
        if conn:
            conn.close()
        return False

def get_job_status(job_id):
    """Get job status from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT ij.*, r.name as restaurant_name
                FROM image_upload_jobs ij
                LEFT JOIN restaurants r ON ij.restaurant_id = r.id
                WHERE ij.id = %s
            """, (job_id,))
            
            result = cur.fetchone()
            conn.close()
            
            if result:
                return {
                    'id': result['id'],
                    'restaurant_id': result['restaurant_id'],
                    'restaurant_name': result['restaurant_name'],
                    'filename': result['filename'],
                    'status': result['status'],
                    'created_at': result['created_at'].isoformat(),
                    'completed_at': result['completed_at'].isoformat() if result['completed_at'] else None
                }
            return None
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        if conn:
            conn.close()
        return None

def publish_status_update(job_id, status_data):
    """Publish status update to Redis for SSE"""
    if r:
        try:
            import json
            r.publish(f"upload_status:{job_id}", json.dumps(status_data))
            return True
        except Exception as e:
            logger.error(f"Error publishing status update: {e}")
            return False
    return False

@celery.task(bind=True)
def process_image(self, job_id, restaurant_id, filename):
    """Background task to process uploaded image"""
    try:
        logger.info(f"Starting image processing for job {job_id}")
        
        # Update status to processing
        update_job_status(job_id, 'processing')
        publish_status_update(job_id, {
            'status': 'processing',
            'message': 'Starting image processing...',
            'progress': 10
        })
        
        # File paths
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        output_dir = os.path.join(app.config['PROCESSED_FOLDER'], str(restaurant_id))
        os.makedirs(output_dir, exist_ok=True)
        
        if not os.path.exists(input_path):
            raise Exception(f"Input file not found: {input_path}")
        
        # Open and validate image
        publish_status_update(job_id, {
            'status': 'processing',
            'message': 'Validating image...',
            'progress': 20
        })
        
        with Image.open(input_path) as img:
            # Validate image format
            if img.format.lower() not in ['jpeg', 'png', 'gif', 'webp']:
                raise Exception(f"Unsupported image format: {img.format}")
            
            # Get original dimensions
            original_width, original_height = img.size
            logger.info(f"Original image size: {original_width}x{original_height}")
            
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Generate processed filenames
            base_name = os.path.splitext(filename)[0]
            
            # 1. Create optimized version
            publish_status_update(job_id, {
                'status': 'processing',
                'message': 'Creating optimized version...',
                'progress': 40
            })
            
            optimized_filename = f"{base_name}_optimized.jpg"
            optimized_path = os.path.join(output_dir, optimized_filename)
            
            # Resize if too large
            if original_width > MAX_IMAGE_SIZE[0] or original_height > MAX_IMAGE_SIZE[1]:
                img.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
                logger.info(f"Resized to: {img.size}")
            
            # Save optimized version with compression
            img.save(optimized_path, 'JPEG', quality=85, optimize=True)
            
            # 2. Create thumbnail
            publish_status_update(job_id, {
                'status': 'processing',
                'message': 'Creating thumbnail...',
                'progress': 60
            })
            
            thumbnail_filename = f"{base_name}_thumb.jpg"
            thumbnail_path = os.path.join(output_dir, thumbnail_filename)
            
            # Create thumbnail
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            img.save(thumbnail_path, 'JPEG', quality=80, optimize=True)
            
            # 3. Quality checks
            publish_status_update(job_id, {
                'status': 'processing',
                'message': 'Performing quality checks...',
                'progress': 80
            })
            
            # Check file sizes
            optimized_size = os.path.getsize(optimized_path)
            thumbnail_size = os.path.getsize(thumbnail_path)
            
            # Simulate processing time based on original file size
            original_size = os.path.getsize(input_path)
            processing_time = min(max(original_size / (1024 * 1024), 1), 10)  # 1-10 seconds
            time.sleep(processing_time)
            
            # 4. Update menu item with image URL (if applicable)
            publish_status_update(job_id, {
                'status': 'processing',
                'message': 'Updating database...',
                'progress': 90
            })
            
            # Generate URLs (in real app, these would be actual URLs)
            optimized_url = f"/images/{restaurant_id}/{optimized_filename}"
            thumbnail_url = f"/images/{restaurant_id}/{thumbnail_filename}"
            
            # 5. Final status update
            completed_at = datetime.now()
            update_job_status(job_id, 'completed', completed_at)
            
            # Publish completion
            publish_status_update(job_id, {
                'status': 'completed',
                'message': 'Image processing completed successfully!',
                'progress': 100,
                'results': {
                    'original_size': original_size,
                    'optimized_size': optimized_size,
                    'thumbnail_size': thumbnail_size,
                    'optimized_url': optimized_url,
                    'thumbnail_url': thumbnail_url,
                    'dimensions': f"{original_width}x{original_height}",
                    'processed_at': completed_at.isoformat()
                }
            })
            
            # Cleanup original file
            try:
                os.remove(input_path)
            except:
                pass
            
            logger.info(f"Image processing completed for job {job_id}")
            return {
                'status': 'completed',
                'optimized_url': optimized_url,
                'thumbnail_url': thumbnail_url
            }
            
    except Exception as e:
        logger.error(f"Image processing failed for job {job_id}: {str(e)}")
        
        # Update status to failed
        update_job_status(job_id, 'failed')
        publish_status_update(job_id, {
            'status': 'failed',
            'message': f'Image processing failed: {str(e)}',
            'progress': 0,
            'error': str(e)
        })
        
        # Cleanup files on failure
        try:
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(input_path):
                os.remove(input_path)
        except:
            pass
            
        raise

@app.route("/api/upload", methods=["POST"])
def upload_image():
    """Upload image endpoint"""
    try:
        # Validate request
        if 'image' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No image file provided'
            }), 400
            
        file = request.files['image']
        restaurant_id = request.form.get('restaurant_id')
        
        if not restaurant_id:
            return jsonify({
                'success': False,
                'error': 'Restaurant ID is required'
            }), 400
            
        try:
            restaurant_id = int(restaurant_id)
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid restaurant ID'
            }), 400
            
        if not validate_restaurant(restaurant_id):
            return jsonify({
                'success': False,
                'error': 'Restaurant not found'
            }), 404
            
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
            
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400
            
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        unique_id = str(uuid.uuid4())
        unique_filename = f"{unique_id}.{file_extension}"
        
        os.makedirs("uploads", exist_ok=True)
        # Save file
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        # Validate file size
        file_size = os.path.getsize(filepath)
        if file_size > app.config['MAX_CONTENT_LENGTH']:
            os.remove(filepath)
            return jsonify({
                'success': False,
                'error': 'File too large'
            }), 413
            
        # Create database record
        job_id = create_upload_job(restaurant_id, original_filename, unique_filename)
        if not job_id:
            os.remove(filepath)
            return jsonify({
                'success': False,
                'error': 'Failed to create upload job'
            }), 500
            
        # Start background processing
        task = process_image.apply_async(args=[job_id, restaurant_id, unique_filename])
        
        # Initial status update
        publish_status_update(job_id, {
            'status': 'uploaded',
            'message': 'File uploaded successfully, processing started...',
            'progress': 5,
            'job_id': job_id,
            'task_id': task.id,
            'filename': original_filename,
            'file_size': file_size
        })
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'task_id': task.id,
            'filename': original_filename,
            'file_size': file_size,
            'message': 'File uploaded successfully, processing started'
        })
        
    except Exception as e:
        logger.error(f"Error in upload endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Upload failed'
        }), 500

@app.route("/api/upload/status/<int:job_id>")
def upload_status_sse(job_id):
    """SSE endpoint for upload status updates"""
    
    # Validate job exists
    job = get_job_status(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    def event_stream():
        try:
            import json
            
            # Send initial status
            yield f"data: {json.dumps(job)}\n\n"
            
            if not r:
                yield f"data: {json.dumps({'error': 'Real-time updates unavailable'})}\n\n"
                return
                
            # Subscribe to Redis updates for this job
            pubsub = r.pubsub()
            pubsub.subscribe(f"upload_status:{job_id}")
            
            # Listen for updates
            for message in pubsub.listen():
                try:
                    if message["type"] == "message":
                        status_data = json.loads(message["data"])
                        yield f"data: {json.dumps(status_data)}\n\n"
                        
                        # Stop streaming if job is completed or failed
                        if status_data.get('status') in ['completed', 'failed']:
                            break
                            
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.error(f"Error processing SSE message: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in SSE stream: {e}")
            yield f"data: {json.dumps({'error': 'Stream error occurred'})}\n\n"
    
    response = Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
    
    return response

@app.route("/api/upload/status/<int:job_id>/json")
def upload_status_json(job_id):
    """REST API endpoint for job status"""
    job = get_job_status(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
        
    return jsonify({
        'success': True,
        'job': job
    })

@app.route("/api/uploads/<int:restaurant_id>")
def get_restaurant_uploads(restaurant_id):
    """Get all uploads for a restaurant"""
    try:
        if not validate_restaurant(restaurant_id):
            return jsonify({'error': 'Restaurant not found'}), 404
            
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 500
            
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM image_upload_jobs 
                WHERE restaurant_id = %s 
                ORDER BY created_at DESC 
                LIMIT 50
            """, (restaurant_id,))
            
            jobs = cur.fetchall()
            
        conn.close()
        
        return jsonify({
            'success': True,
            'uploads': [{
                'id': job['id'],
                'filename': job['filename'],
                'status': job['status'],
                'created_at': job['created_at'].isoformat(),
                'completed_at': job['completed_at'].isoformat() if job['completed_at'] else None
            } for job in jobs]
        })
        
    except Exception as e:
        logger.error(f"Error getting restaurant uploads: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get uploads'
        }), 500

@app.route("/health")
def health():
    """Health check endpoint"""
    redis_status = "ok" if r and r.ping() else "error"
    db_status = "ok" if get_db_connection() else "error"
    celery_status = "ok"  # Would need actual celery health check
    
    return jsonify({
        "status": "ok",
        "service": "image_upload",
        "redis": redis_status,
        "database": db_status,
        "celery": celery_status
    })

@app.errorhandler(413)
def too_large(e):
    return jsonify({
        'success': False,
        'error': 'File too large'
    }), 413

# Add CORS headers
@app.after_request
def after_request(response):
    """Add CORS headers to all responses"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Accept')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    response.headers.add('Access-Control-Expose-Headers', '*')
    return response

# Add OPTIONS handler for preflight requests
@app.route("/api/upload", methods=["OPTIONS"])
def upload_options():
    return "", 204

@app.route("/api/uploads/<int:restaurant_id>", methods=["OPTIONS"])
def uploads_options():
    return "", 204

if __name__ == "__main__":
    # Initialize directories
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

    # Test database connection with retry
    conn = get_db_connection()
    if conn:
        logger.info("Database connection successful")
        conn.close()
    else:
        logger.error("Failed to connect to database")
        
    # Test Redis with retry
    redis_connected = False
    for i in range(5):
        try:
            if r and r.ping():
                logger.info("Redis connection successful")
                redis_connected = True
                break
            time.sleep(2)
        except:
            logger.error(f"Redis connection attempt {i+1} failed")
    
    if not redis_connected:
        logger.error("All Redis connection attempts failed")
            
    app.run(host="0.0.0.0", port=5007, threaded=True, debug=True)  # Changed port to 5007