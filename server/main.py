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

def process_video_request(task_id, prompt, settings):
    """Process a video generation request"""
    try:
        logger.info(f"Starting video generation for task {task_id} with prompt: {prompt[:50]}...")
        
        # Update initial status
        update_task_status(task_id, {
            "status": "processing",
            "message": "Starting video generation...",
            "progress": 10,
            "started_at": datetime.now().isoformat()
        })
        
        # Generate video using ZhipuAI client
        response = client.videos.generations(
            model=settings.get('model', VIDEO_SETTINGS['model']),
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
            "progress": 20
        })
        
        # Start polling for this request
        poll_video_status(task_id, api_task_id)
        
    except Exception as e:
        logger.error(f"Error processing video request for task {task_id}: {str(e)}")
        update_task_status(task_id, {
            "status": "error",
            "message": f"Error processing request: {str(e)}"
        })

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
        
        # Initialize task status
        update_task_status(task_id, {
            "status": "processing",
            "message": "Starting video generation...",
            "created_at": datetime.now().isoformat(),
            "progress": 0,
            "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt
        })
        
        # Process the request in a background thread
        thread = threading.Thread(
            target=process_video_request,
            args=(task_id, prompt, settings),
            daemon=True,
            name=f"video_gen_{task_id}"
        )
        thread.start()
        
        return jsonify({
            "message": "Video generation started",
            "taskId": task_id,
            "estimatedTime": "30-60 seconds"
        }), 202

    except Exception as e:
        logger.error(f"Server Error in generate_video: {str(e)}")
        return jsonify({
            "error": str(e),
            "message": "Failed to start video generation"
        }), 500

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
        "redis_status": redis_status
    }), 200

if __name__ == '__main__':
    try:
        # Run the Flask app
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"Starting server on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)