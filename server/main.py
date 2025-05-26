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
import signal
import sys

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] %(message)s'
)
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

# Your API key from environment variable (more secure)
API_KEY = os.getenv('ZHIPU_API_KEY', 'd000d59e55c244cbb7c8cfecede59772.cmirhsiseKY8NNuh')

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
MAX_CONCURRENT_REQUESTS = 1  # Reduced for Render's resource limits
request_queue = Queue()
active_requests = set()
queue_lock = threading.Lock()

# Polling configuration
MAX_RETRIES = 60   # Reduced to 5 minutes total
RETRY_DELAY = 5    # 5 seconds between each check
QUEUE_CHECK_INTERVAL = 2  # Check queue every 2 seconds

# Thread pool for handling video generation tasks
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS, thread_name_prefix="video_gen")

# Global shutdown flag
shutdown_flag = threading.Event()

# Configure Redis with better error handling
try:
    REDIS_URL = os.getenv('REDIS_URL', 'redis://red-d0qb0h0dl3ps73eq55dg:6379')
    redis_client = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=10, socket_connect_timeout=10)
    # Test connection
    redis_client.ping()
    logger.info("Redis connection established successfully")
except Exception as e:
    logger.error(f"Redis connection failed: {e}")
    redis_client = None

def get_task_status(task_id):
    """Get task status from Redis with fallback to memory"""
    if not redis_client:
        return None
    try:
        status = redis_client.get(f"task:{task_id}")
        return json.loads(status) if status else None
    except Exception as e:
        logger.error(f"Error getting task status from Redis: {e}")
        return None

def update_task_status(task_id, status_update):
    """Update task status in Redis with fallback"""
    if not redis_client:
        logger.warning("Redis not available, status update skipped")
        return
    
    try:
        # Get existing status
        current_status = get_task_status(task_id) or {}
        # Update with new data
        current_status.update(status_update)
        current_status['updated_at'] = datetime.now().isoformat()
        
        # Save back to Redis with 2 hour expiry
        redis_client.setex(
            f"task:{task_id}",
            7200,  # 2 hours expiry
            json.dumps(current_status)
        )
        logger.info(f"Updated task {task_id} status: {status_update}")
    except Exception as e:
        logger.error(f"Error updating task status in Redis: {e}")

def get_task_mapping(task_id):
    """Get task ID mapping from Redis"""
    if not redis_client:
        return None
    try:
        return redis_client.get(f"mapping:{task_id}")
    except Exception as e:
        logger.error(f"Error getting task mapping from Redis: {e}")
        return None

def set_task_mapping(internal_id, api_id):
    """Set task ID mapping in Redis"""
    if not redis_client:
        return
    try:
        # Save mapping both ways with 2 hour expiry
        redis_client.setex(f"mapping:{internal_id}", 7200, api_id)
        redis_client.setex(f"mapping:{api_id}", 7200, internal_id)
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
            ] if hasattr(response, 'video_result') else [],
            'id': getattr(response, 'id', None)
        }
    except Exception as e:
        logger.error(f"Error handling API response: {str(e)}")
        return None

def poll_video_status(internal_task_id, api_task_id):
    """Poll for video generation status until completion or failure"""
    total_wait_time = 0
    start_time = time.time()
    
    logger.info(f"Starting to poll video status for task {internal_task_id} (API ID: {api_task_id})")
    
    while total_wait_time < (MAX_RETRIES * RETRY_DELAY) and not shutdown_flag.is_set():
        try:
            logger.info(f"Polling attempt for task {internal_task_id}, elapsed: {total_wait_time}s")
            
            status_response = client.videos.retrieve_videos_result(id=api_task_id)
            response_data = handle_api_response(status_response)
            
            if not response_data:
                logger.error(f"Failed to retrieve video status for task {internal_task_id}")
                update_task_status(internal_task_id, {
                    "status": "error",
                    "message": "Failed to retrieve video status",
                    "api_task_id": api_task_id
                })
                return
            
            task_status = response_data.get('task_status', '').upper()
            current_time = time.time()
            time_elapsed = current_time - start_time
            
            logger.info(f"Task {internal_task_id} status: {task_status}")
            
            if task_status == 'SUCCESS':
                video_results = response_data.get('video_result', [])
                if video_results and len(video_results) > 0:
                    video_result = video_results[0]
                    update_task_status(internal_task_id, {
                        "status": "success",
                        "videoUrl": video_result.get('url'),
                        "coverImageUrl": video_result.get('cover_image_url'),
                        "model": response_data.get('model'),
                        "timeElapsed": round(time_elapsed),
                        "api_task_id": api_task_id,
                        "completed_at": datetime.now().isoformat()
                    })
                    logger.info(f"Task {internal_task_id} completed successfully")
                    return
                else:
                    update_task_status(internal_task_id, {
                        "status": "error",
                        "message": "No video result found",
                        "api_task_id": api_task_id
                    })
                    return
            
            elif task_status == 'FAILED':
                update_task_status(internal_task_id, {
                    "status": "error",
                    "message": "Video generation failed",
                    "api_task_id": api_task_id
                })
                logger.error(f"Task {internal_task_id} failed")
                return
            
            # Update progress for frontend
            progress = min(round((time_elapsed / 300) * 100), 95)  # 5 minute estimate
            update_task_status(internal_task_id, {
                "status": "processing",
                "progress": progress,
                "timeElapsed": round(time_elapsed),
                "message": f"Generating video ({progress}% complete)",
                "api_task_id": api_task_id
            })
            
            time.sleep(RETRY_DELAY)
            total_wait_time += RETRY_DELAY
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error polling task {internal_task_id}: {error_msg}")
            
            if "任务不存在" in error_msg or "task does not exist" in error_msg.lower():
                if time_elapsed < 120:  # Wait up to 2 minutes for task to appear
                    logger.info(f"Task {internal_task_id} not found yet, retrying...")
                    time.sleep(RETRY_DELAY)
                    total_wait_time += RETRY_DELAY
                    continue
                    
            update_task_status(internal_task_id, {
                "status": "error",
                "message": f"Error during video generation: {str(e)}",
                "api_task_id": api_task_id
            })
            return
    
    # If we get here, we've timed out
    logger.error(f"Task {internal_task_id} timed out")
    update_task_status(internal_task_id, {
        "status": "error",
        "message": "Video generation timed out",
        "api_task_id": api_task_id
    })

def process_queue():
    """Process requests from the queue when slots are available"""
    logger.info("Queue processor thread started")
    
    while not shutdown_flag.is_set():
        try:
            current_active = len(active_requests)
            current_queue_size = request_queue.qsize()
            
            if current_active > 0 or current_queue_size > 0:
                logger.info(f"Queue status - Active: {current_active}, Queued: {current_queue_size}")
            
            # Check if we can process more requests
            if current_active < MAX_CONCURRENT_REQUESTS and not request_queue.empty():
                try:
                    # Get next request from queue with timeout
                    request_data = request_queue.get(timeout=1)
                    task_id = request_data['task_id']
                    prompt = request_data['prompt']
                    settings = request_data['settings']
                    
                    logger.info(f"Processing task {task_id} from queue")
                    
                    # Add to active requests before processing
                    with queue_lock:
                        active_requests.add(task_id)
                    
                    # Update status
                    update_task_status(task_id, {
                        "status": "processing",
                        "message": "Starting video generation...",
                        "queue_position": 0,
                        "started_at": datetime.now().isoformat()
                    })
                    
                    # Submit to thread pool instead of processing directly
                    future = executor.submit(process_video_request, task_id, prompt, settings)
                    logger.info(f"Task {task_id} submitted to thread pool")
                    
                except Exception as e:
                    logger.error(f"Error processing queue item: {str(e)}")
            
            # Update queue positions for waiting tasks
            update_queue_positions()
            
            time.sleep(QUEUE_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in queue processing: {str(e)}")
            time.sleep(QUEUE_CHECK_INTERVAL)
    
    logger.info("Queue processor thread stopped")

def process_video_request(task_id, prompt, settings):
    """Process a single video generation request"""
    try:
        logger.info(f"Starting video generation for task {task_id} with prompt: {prompt[:50]}...")
        
        # Generate video using ZhipuAI client
        response = client.videos.generations(
            model=settings['model'],
            prompt=prompt,
            quality=settings.get('quality', 'quality'),
            with_audio=settings.get('with_audio', False),
            size=settings.get('size', '1920x1080'),
            fps=settings.get('fps', 30)
        )
        
        # Get the task ID from the response
        api_task_id = getattr(response, 'id', None)
        if not api_task_id:
            raise Exception("No task ID received from API")
            
        logger.info(f"Received API task ID: {api_task_id} for internal task ID: {task_id}")
        
        # Update the task ID mapping and status
        set_task_mapping(task_id, api_task_id)
        update_task_status(task_id, {
            "status": "processing",
            "message": "Video generation in progress...",
            "api_task_id": api_task_id,
            "queue_position": 0,
            "progress": 10
        })
        
        # Start polling for this request
        poll_video_status(task_id, api_task_id)
        
    except Exception as e:
        logger.error(f"Error processing video request for task {task_id}: {str(e)}")
        update_task_status(task_id, {
            "status": "error",
            "message": f"Error processing request: {str(e)}"
        })
    finally:
        # Remove from active requests when done
        with queue_lock:
            active_requests.discard(task_id)
            logger.info(f"Task {task_id} removed from active requests. Active: {len(active_requests)}")

def update_queue_positions():
    """Update queue positions for all waiting requests"""
    if not redis_client:
        return
    
    try:
        # Get all task keys from Redis
        task_keys = redis_client.keys("task:*")
        queued_tasks = []
        
        for task_key in task_keys:
            task_id = task_key.split(":")[1]
            task_data = get_task_status(task_id)
            if task_data and task_data.get("status") == "queued":
                created_at = task_data.get("created_at", "")
                queued_tasks.append((task_id, created_at))
        
        # Sort by creation time
        queued_tasks.sort(key=lambda x: x[1])
        
        # Update positions
        for position, (task_id, _) in enumerate(queued_tasks, 1):
            update_task_status(task_id, {
                "queue_position": position,
                "message": f"Waiting in queue (Position: {position})"
            })
            
    except Exception as e:
        logger.error(f"Error updating queue positions: {str(e)}")

def cleanup_old_tasks():
    """Cleanup completed tasks periodically"""
    logger.info("Cleanup thread started")
    
    while not shutdown_flag.is_set():
        try:
            if redis_client:
                # Get all task keys from Redis
                task_keys = redis_client.keys("task:*")
                total_tasks = len(task_keys)
                completed_tasks = 0
                
                for task_key in task_keys:
                    task_id = task_key.split(":")[1]
                    task_data = get_task_status(task_id)
                    if task_data and task_data.get("status") in ["success", "error"]:
                        completed_tasks += 1
                
                if total_tasks > 0:
                    logger.info(f"Task status: {completed_tasks} completed out of {total_tasks} total")
            
        except Exception as e:
            logger.error(f"Error in cleanup task: {str(e)}")
        
        shutdown_flag.wait(300)  # Wait 5 minutes or until shutdown
    
    logger.info("Cleanup thread stopped")

def graceful_shutdown(signum, frame):
    """Handle graceful shutdown"""
    logger.info("Received shutdown signal, stopping gracefully...")
    shutdown_flag.set()
    executor.shutdown(wait=True, timeout=30)
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    try:
        if redis_client:
            redis_client.ping()
            redis_status = "connected"
        else:
            redis_status = "not available"
    except Exception as e:
        redis_status = f"error: {str(e)}"

    return jsonify({
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": time.time(),
        "active_tasks": len(active_requests),
        "queued_tasks": request_queue.qsize(),
        "redis_status": redis_status,
        "max_concurrent": MAX_CONCURRENT_REQUESTS
    }), 200

@app.route('/queue-status', methods=['GET'])
def queue_status():
    """Get detailed queue status"""
    try:
        active_list = list(active_requests)
        queue_size = request_queue.qsize()
        
        # Get queued task details from Redis
        queued_details = []
        if redis_client:
            try:
                task_keys = redis_client.keys("task:*")
                for task_key in task_keys:
                    task_id = task_key.split(":")[1]
                    task_data = get_task_status(task_id)
                    if task_data and task_data.get("status") == "queued":
                        queued_details.append({
                            "task_id": task_id,
                            "position": task_data.get("queue_position", 0),
                            "created_at": task_data.get("created_at", "")
                        })
            except Exception as e:
                logger.error(f"Error getting queued task details: {e}")
        
        return jsonify({
            "active_tasks": active_list,
            "queue_size": queue_size,
            "queued_tasks": queued_details,
            "max_concurrent": MAX_CONCURRENT_REQUESTS
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Start background threads only once
if not shutdown_flag.is_set():
    logger.info("Initializing background threads...")
    
    # Start queue processor thread
    queue_processor = threading.Thread(target=process_queue, daemon=True, name="queue_processor")
    queue_processor.start()
    logger.info("Queue processor thread started")
    
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_old_tasks, daemon=True, name="cleanup")
    cleanup_thread.start()
    logger.info("Cleanup thread started")

logger.info("Server initialization complete")

@app.route('/generate-video', methods=['POST'])
def generate_video():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        prompt = data.get('prompt', '').strip()
        
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

        # Generate unique task ID with timestamp and random component
        import random
        task_id = f"task_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        logger.info(f"Generated new task ID: {task_id} for prompt: {prompt[:50]}...")
        
        # Calculate queue position
        queue_position = request_queue.qsize() + 1
        
        # Initialize task status
        update_task_status(task_id, {
            "status": "queued",
            "queue_position": queue_position,
            "message": f"Waiting in queue (Position: {queue_position})",
            "created_at": datetime.now().isoformat(),
            "progress": 0,
            "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt
        })
        
        # Add to queue
        request_queue.put({
            "task_id": task_id,
            "prompt": prompt,
            "settings": settings
        })
        
        logger.info(f"Added task {task_id} to queue. Queue size: {request_queue.qsize()}")
        
        return jsonify({
            "message": "Request queued successfully",
            "taskId": task_id,
            "queuePosition": queue_position,
            "estimatedWaitTime": f"{queue_position * 30} seconds"
        }), 202

    except Exception as e:
        logger.error(f"Server Error in generate_video: {str(e)}")
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
        "message": "Task not found. The task may have expired or never existed."
    }), 404

if __name__ == '__main__':
    try:
        # Run the Flask app
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"Starting server on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        shutdown_flag.set()
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)