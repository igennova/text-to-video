from flask import Flask, request, jsonify
import requests
import json
from flask_cors import CORS
from zhipuai import ZhipuAI
from dotenv import load_dotenv
import os

# Initialize Flask application
app = Flask(__name__)
load_dotenv()
CORS(app)
# Your API key from Zhipu AI
API_KEY =os.getenv('API_KEY')

# ZhipuAI client setup
client = ZhipuAI(api_key=API_KEY)

# Define the request URL and headers for video generation
url = 'https://open.bigmodel.cn/api/paas/v4/videos/generations'
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {API_KEY}'
}

# Route to initiate video generation
@app.route('/generate-video', methods=['POST'])
def generate_video():
    try:
        # Get the prompt from the incoming POST request
        data = request.get_json()
        prompt = data.get('prompt', 'Default prompt text')

        # Define the request payload
        payload = {
            'model': 'cogvideox',
            'prompt': prompt
        }

        # Make the POST request to initiate video generation
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response_data = response.json()

        # Check if we got an ID for the video generation task
        if 'id' in response_data:
            video_id = response_data['id']
            return jsonify({"message": "Video generation started", "id": video_id}), 200
        else:
            return jsonify({"error": "Failed to start video generation"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to check the result of the video generation
@app.route('/check-video-result', methods=['POST'])
def check_video_result():
    try:
        # Get the video generation ID from the request
        data = request.get_json()
        video_id = data.get('id')

        if not video_id:
            return jsonify({"error": "No video generation ID provided"}), 400

        # Use the ZhipuAI client to check the video result
        response = client.videos.retrieve_videos_result(id=video_id)
    

        # If the task is successful, return the video URL and cover image URL
        if response.task_status == 'SUCCESS':
            video_url = response.video_result[0].url
            cover_image_url = response.video_result[0].cover_image_url
            print(video_url)
            return jsonify({"message": "Video generation successful", "video_url": video_url, "cover_image_url": cover_image_url}), 200
        else:
            return jsonify({"message": "Video generation in progress", "task_status": response.task_status}), 202

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Run the Flask application
if __name__ == '__main__':
    app.run(debug=True)
