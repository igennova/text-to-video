from flask import Flask, request, jsonify
import requests
import json
from flask_cors import CORS
from zhipuai import ZhipuAI
from dotenv import load_dotenv
import os
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from datetime import datetime
import redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)
load_dotenv()

# Configure CORS to allow requests from your frontend domain
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:3000",
            "http://localhost:5173",
            "https://text-to-video-1wr1.onrender.com",
            "https://text-to-video-backend1.onrender.com"
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Your API key from Zhipu AI
API_KEY = 'd000d59e55c244cbb7c8cfecede59772.cmirhsiseKY8NNuh'

# ZhipuAI client setup
client = ZhipuAI(api_key=API_KEY)

# Video generation settings
VIDEO_SETTINGS = {
    'model': 'cogvideox-flash',
    'quality': 'quality',
    'with_audio': False,
    'size': '1920x1080',
    'fps': 30
}

# Queue configuration
MAX_CONCURRENT_REQUESTS = 2
request_queue = Queue()
active_requests = set()
queue_lock = threading.Lock()

# Polling configuration
MAX_RETRIES = 120  # 10 minutes total maximum wait time
RETRY_DELAY = 5    # 5 seconds between each check

# Thread pool for handling video generation tasks
executor = ThreadPoolExecutor(max_workers=5)

# Task ID mapping
task_id_mapping = {}

# Store for video generation tasks (use a dictionary with lock for thread safety)
video_tasks = {}
tasks_lock = threading.Lock()

# Configure Redis
REDIS_URL = os.getenv('REDIS_URL', 'redis://red-d0qb0h0dl3ps73eq55dg:6379')
redis_client = redis.from_url(REDIS_URL)

def get_task_status(task_id):
    """Get task status from Redis"""
    try:
        status = redis_client.get(f"task:{task_id}")
        return json.loads(status) if status else None
    except Exception as e:
        logger.error(f"Error getting task status from Redis: {e}")
        return None

def update_task_status(task_id, status_update):
    """Update task status in Redis"""
    try:
        # Get existing status
        current_status = get_task_status(task_id) or {}
        # Update with new data
        current_status.update(status_update)
        # Save back to Redis with 1 hour expiry
        redis_client.setex(
            f"task:{task_id}",
            3600,  # 1 hour expiry
            json.dumps(current_status)
        )
        logger.info(f"Updated task {task_id} status: {status_update}")
    except Exception as e:
        logger.error(f"Error updating task status in Redis: {e}")

def get_task_mapping(task_id):
    """Get task ID mapping from Redis"""
    try:
        return redis_client.get(f"mapping:{task_id}")
    except Exception as e:
        logger.error(f"Error getting task mapping from Redis: {e}")
        return None

def set_task_mapping(internal_id, api_id):
    """Set task ID mapping in Redis"""
    try:
        # Save mapping both ways with 1 hour expiry
        redis_client.setex(f"mapping:{internal_id}", 3600, api_id)
        redis_client.setex(f"mapping:{api_id}", 3600, internal_id)
        logger.info(f"Mapped task IDs: {internal_id} <-> {api_id}")
    except Exception as e:
        logger.error(f"Error setting task mapping in Redis: {e}")

def handle_api_response(response):
    """Helper function to handle API response and extract relevant data"""
    try:
        if isinstance(response, dict):
            return response
        # Convert response object to dictionary if it's not already
        return {
            'model': getattr(response, 'model', VIDEO_SETTINGS['model']),
            'request_id': getattr(response, 'request_id', None),
            'task_status': getattr(response, 'task_status', None),
            'video_result': [
                {
                    'url': getattr(item, 'url', None),
                    'cover_image_url': getattr(item, 'cover_image_url', None)
                } for item in (getattr(response, 'video_result', []) or [])
            ] if hasattr(response, 'video_result') else []
        }
    except Exception as e:
        logger.error(f"Error handling API response: {str(e)}")
        return None

def format_task_id(task_id):
    """Format task ID to ensure it's in the correct format"""
    # Remove any unwanted characters and ensure proper format
    # task_id = str(task_id).strip()
    return task_id

def poll_video_status(internal_task_id, api_task_id):
    """Poll for video generation status until completion or failure"""
    total_wait_time = 0
    start_time = time.time()
    
    while total_wait_time < (MAX_RETRIES * RETRY_DELAY):
        try:
            status_response = client.videos.retrieve_videos_result(id=api_task_id)
            response_data = handle_api_response(status_response)
            
            if not response_data:
                video_tasks[internal_task_id] = {
                    "status": "error",
                    "message": "Failed to retrieve video status",
                    "api_task_id": api_task_id
                }
                return
            
            task_status = response_data.get('task_status', '').upper()
            current_time = time.time()
            time_elapsed = current_time - start_time
            
            if task_status == 'SUCCESS':
                video_results = response_data.get('video_result', [])
                if video_results and len(video_results) > 0:
                    video_result = video_results[0]
                    video_tasks[internal_task_id] = {
                        "status": "success",
                        "videoUrl": video_result.get('url'),
                        "coverImageUrl": video_result.get('cover_image_url'),
                        "model": response_data.get('model'),
                        "timeElapsed": round(time_elapsed),
                        "api_task_id": api_task_id
                    }
                    return
                else:
                    video_tasks[internal_task_id] = {
                        "status": "error",
                        "message": "No video result found",
                        "api_task_id": api_task_id
                    }
                    return
            
            elif task_status == 'FAILED':
                video_tasks[internal_task_id] = {
                    "status": "error",
                    "message": "Video generation failed",
                    "api_task_id": api_task_id
                }
                return
            
            # Update progress for frontend
            progress = min(round((time_elapsed / 120) * 100), 95)
            video_tasks[internal_task_id] = {
                "status": "processing",
                "progress": progress,
                "timeElapsed": round(time_elapsed),
                "message": f"Generating video ({progress}% complete)",
                "api_task_id": api_task_id
            }
            
            time.sleep(RETRY_DELAY)
            total_wait_time += RETRY_DELAY
            
        except Exception as e:
            error_msg = str(e)
            if "任务不存在" in error_msg or "task does not exist" in error_msg.lower():
                if time_elapsed < 300:  # Still within 5 minutes timeout
                    time.sleep(RETRY_DELAY)
                    total_wait_time += RETRY_DELAY
                    continue
                    
            video_tasks[internal_task_id] = {
                "status": "error",
                "message": f"Error during video generation: {str(e)}",
                "api_task_id": api_task_id
            }
            return
    
    # If we get here, we've timed out
    video_tasks[internal_task_id] = {
        "status": "error",
        "message": "Video generation timed out",
        "api_task_id": api_task_id
    }

def process_queue():
    """Process requests from the queue when slots are available"""
    while True:
        try:
            # Check if we can process more requests
            with queue_lock:
                if len(active_requests) < MAX_CONCURRENT_REQUESTS and not request_queue.empty():
                    # Get next request from queue
                    request_data = request_queue.get()
                    task_id = request_data['task_id']
                    prompt = request_data['prompt']
                    settings = request_data['settings']
                    
                    # Add to active requests
                    active_requests.add(task_id)
                    
                    # Update status
                    update_task_status(task_id, {
                        "status": "processing",
                        "message": "Starting video generation...",
                        "queue_position": 0,
                        "started_at": datetime.now().isoformat()
                    })
                    
                    # Start processing in background
                    executor.submit(process_video_request, task_id, prompt, settings)
            
            time.sleep(1)  # Prevent busy waiting
        except Exception as e:
            logger.error(f"Error in queue processing: {str(e)}")
            time.sleep(1)  # Wait before retrying

def process_video_request(task_id, prompt, settings):
    """Process a single video generation request"""
    try:
        logger.info(f"Processing video request for task {task_id}")
        # Generate video using ZhipuAI client
        response = client.videos.generations(
            model=settings['model'],
            prompt=prompt,
            quality=settings['quality'],
            with_audio=settings['with_audio'],
            size=settings['size'],
            fps=settings['fps']
        )
        
        # Get the task ID from the response using the id attribute
        api_task_id = getattr(response, 'id', None)
        if not api_task_id:
            raise Exception("No task ID received from API")
            
        logger.info(f"Received API task ID: {api_task_id} for internal task ID: {task_id}")
        
        # Update the task ID mapping and status
        with queue_lock:
            task_id_mapping[task_id] = api_task_id
            update_task_status(task_id, {
                "status": "processing",
                "message": "Starting video generation...",
                "api_task_id": api_task_id,
                "queue_position": 0
            })
        
        # Start polling for this request
        poll_video_status(task_id, api_task_id)
        
    except Exception as e:
        logger.error(f"Error processing video request: {str(e)}")
        update_task_status(task_id, {
            "status": "error",
            "message": f"Error processing request: {str(e)}"
        })
    finally:
        # Remove from active requests when done
        with queue_lock:
            active_requests.discard(task_id)
            update_queue_positions()

def update_queue_positions():
    """Update queue positions for all waiting requests"""
    position = 1
    for task_id in video_tasks:
        if video_tasks[task_id].get("status") == "queued":
            video_tasks[task_id].update({
                "queue_position": position,
                "message": f"Waiting in queue (Position: {position})"
            })
            position += 1

# Start queue processing thread
queue_processor = threading.Thread(target=process_queue, daemon=True)
queue_processor.start()

@app.route('/generate-video', methods=['POST'])
def generate_video():
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400

        # Get custom settings or use defaults
        settings = {
            'model': data.get('model', VIDEO_SETTINGS['model']),
            'quality': data.get('quality', VIDEO_SETTINGS['quality']),
            'with_audio': data.get('with_audio', VIDEO_SETTINGS['with_audio']),
            'size': data.get('size', VIDEO_SETTINGS['size']),
            'fps': data.get('fps', VIDEO_SETTINGS['fps'])
        }

        # Generate unique task ID
        task_id = f"task_{int(time.time() * 1000)}"
        logger.info(f"Generated new task ID: {task_id}")
        
        # Initialize task status
        queue_position = request_queue.qsize() + 1
        update_task_status(task_id, {
            "status": "queued",
            "queue_position": queue_position,
            "message": f"Waiting in queue (Position: {queue_position})",
            "created_at": datetime.now().isoformat(),
            "progress": 0
        })
        
        # Add to queue
        request_queue.put({
            "task_id": task_id,
            "prompt": prompt,
            "settings": settings
        })
        
        return jsonify({
            "message": "Request queued successfully",
            "taskId": task_id,
            "queuePosition": queue_position
        }), 202

    except Exception as e:
        logger.error(f"Server Error: {str(e)}")
        return jsonify({
            "error": str(e),
            "message": "Failed to queue video generation request"
        }), 500

@app.route('/check-status/<task_id>', methods=['GET'])
def check_status(task_id):
    """Check the status of a video generation task"""
    logger.info(f"Checking status for task: {task_id}")
    
    # First try to find the task directly
    status = get_task_status(task_id)
    if status:
        return jsonify(status), 200
        
    # If not found, check if it's an API task ID
    internal_id = get_task_mapping(task_id)
    if internal_id:
        status = get_task_status(internal_id)
        if status:
            return jsonify(status), 200
    
    logger.warning(f"Task not found: {task_id}")
    return jsonify({
        "status": "error",
        "message": "Task not found"
    }), 404

# Cleanup completed tasks periodically
def cleanup_old_tasks():
    while True:
        current_time = time.time()
        to_remove = []
        
        for task_id, task_data in video_tasks.items():
            if task_data.get('status') in ['success', 'error']:
                # Keep successful/failed tasks for 1 hour
                if current_time - task_data.get('timeElapsed', 0) > 3600:
                    to_remove.append(task_id)
        
        for task_id in to_remove:
            video_tasks.pop(task_id, None)
            
        time.sleep(3600)  # Run cleanup every hour

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_tasks, daemon=True)
cleanup_thread.start()

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    try:
        # Test Redis connection
        redis_client.ping()
        redis_status = "connected"
    except Exception as e:
        redis_status = f"error: {str(e)}"

    return jsonify({
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": time.time(),
        "active_tasks": len(active_requests),
        "queued_tasks": request_queue.qsize(),
        "redis_status": redis_status
    }), 200

if __name__ == '__main__':
    # Start background threads before running the app
    try:
        # Start queue processor thread
        queue_processor = threading.Thread(target=process_queue, daemon=True)
        queue_processor.start()

        # Start cleanup thread
        cleanup_thread = threading.Thread(target=cleanup_old_tasks, daemon=True)
        cleanup_thread.start()

        # Run the Flask app
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("Shutting down server...")
    except Exception as e:
        print(f"Error starting server: {e}")

