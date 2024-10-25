import React, { useState } from "react";
import axios from "axios";
import Loader from "./components/Loader";
import VideoPlayer from "./components/VideoPlayer";

function App() {
  const [prompt, setPrompt] = useState("");
  const [videoId, setVideoId] = useState("");
  const [videoUrl, setVideoUrl] = useState("");
  const [loading, setLoading] = useState(false);

  const handleGenerateVideo = async () => {
    setVideoUrl("");
    setLoading(true);
    try {
      const response = await axios.post(
        "https://text-to-video-backend1.onrender.com/generate-video",
        { prompt }
      );
      const id = response.data.id;
      setVideoId(id);
      console.log("Generated Video ID:", id);
      setLoading(false);
      alert("Video generation started. Check result after a few moments.");
    } catch (error) {
      console.error("Error generating video", error);
      setLoading(false);
    }
  };

  const handleCheckVideo = async () => {
    setLoading(true);
    try {
      const response = await axios.post(
        "https://text-to-video-backend1.onrender.com/check-video-result",
        { id: videoId }
      );
      console.log("Response from check video:", response.data); // Log the entire response

      if (response.data.video_url) {
        const videoUrl = response.data.video_url;
        setVideoUrl(videoUrl);
        console.log("Video URL:", videoUrl); // Log the retrieved video URL
      } else {
        console.error("Video URL not found in response", response.data);
      }

      setLoading(false);
    } catch (error) {
      console.error("Error fetching video result", error);
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center">
      <h1 className="text-4xl font-bold mb-20 mt-10">AI Video Generator</h1>

      <div className="flex items-center space-x-2 w-full max-w-lg">
        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          className="w-full px-6 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Enter your prompt..."
        />
        <button
          onClick={handleGenerateVideo}
          className="bg-blue-500 text-white px-4 py-3 rounded-lg hover:bg-blue-600 transition duration-200"
        >
          {loading ? <Loader /> : "Search"}
        </button>
      </div>

      {/* {videoId && (
        <div>
          <h3 className="text-white">Video Generation ID: {videoId}</h3>
          <button
            className="text-white"
            onClick={handleCheckVideo}
            style={{ padding: "10px" }}
          >
            Check Video Result
          </button>
        </div>
      )}

      {videoUrl && (
        <div>
          <h3 className="text-white">Your Generated Video:</h3>
          <video width="600" controls>
            <source className="text-white" src={videoUrl} type="video/mp4" />
            Your browser does not support the video tag.
          </video>
        </div>
      )} */}

      {videoId && (
        <button
          onClick={handleCheckVideo}
          className="mt-6 bg-green-500 text-white px-6 py-3 rounded-lg hover:bg-green-600 transition duration-200"
        >
          Check Video Result
        </button>
      )}

      <div className="mt-10">
        {videoUrl && <VideoPlayer source={videoUrl} />}
      </div>
    </div>
  );
}

export default App;
