import React, { useState } from "react";
import axios from "axios";
import Search from "./components/Search";
import Loader from "./components/Loader";

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
        "http://127.0.0.1:5000/generate-video",
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
        "http://127.0.0.1:5000/check-video-result",
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
    <div className="p-5">
      <h1 className="text-white text-2xl font-serif m-5">
        AI Video Generation
      </h1>

      <div className="center">
        <Search
          handleGenerateVideo={handleGenerateVideo}
          prompt={prompt}
          setPrompt={setPrompt}
        />
      </div>

      {videoId && (
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

      {loading && <Loader />}

      {videoUrl && (
        <div>
          <h3 className="text-white">Your Generated Video:</h3>
          <video width="600" controls>
            <source className="text-white" src={videoUrl} type="video/mp4" />
            Your browser does not support the video tag.
          </video>
        </div>
      )}
    </div>
  );
}

export default App;
