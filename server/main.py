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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)
load_dotenv()
CORS(app)

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

# Store for video generation tasks
video_tasks = {}

# Task ID mapping
task_id_mapping = {}

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
                    video_tasks[task_id].update({
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
            
        # Update the task ID mapping
        with queue_lock:
            task_id_mapping[task_id] = api_task_id
            if task_id in video_tasks:
                video_tasks[task_id].update({
                    "api_task_id": api_task_id
                })
        
        # Start polling for this request
        poll_video_status(task_id, api_task_id)
        
    except Exception as e:
        logger.error(f"Error processing video request: {str(e)}")
        video_tasks[task_id].update({
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
        
        # Initialize task status
        queue_position = request_queue.qsize() + 1
        video_tasks[task_id] = {
            "status": "queued",
            "queue_position": queue_position,
            "message": f"Waiting in queue (Position: {queue_position})",
            "created_at": datetime.now().isoformat(),
            "progress": 0
        }
        
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
    # First try to find the task directly
    if task_id in video_tasks:
        task_status = video_tasks[task_id]
        return jsonify(task_status), 200
        
    # If not found, check if it's an API task ID that we're tracking
    for internal_id, api_id in task_id_mapping.items():
        if api_id == task_id and internal_id in video_tasks:
            task_status = video_tasks[internal_id]
            return jsonify(task_status), 200
    
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
    return jsonify({
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": time.time()
    }), 200

if __name__ == '__main__':
    app.run(debug=True)
