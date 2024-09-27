import React, { useState } from 'react';
import axios from 'axios';

function App() {
  const [prompt, setPrompt] = useState('');
  const [videoId, setVideoId] = useState('');
  const [videoUrl, setVideoUrl] = useState('');
  const [loading, setLoading] = useState(false);

  const handleGenerateVideo = async () => {
    setVideoUrl("")
    setLoading(true);
    try {
      const response = await axios.post('http://127.0.0.1:5000/generate-video', { prompt });
      const id = response.data.id;
      setVideoId(id);
      console.log("Generated Video ID:", id);
      setLoading(false);
      alert('Video generation started. Check result after a few moments.');
    } catch (error) {
      console.error("Error generating video", error);
      setLoading(false);
    }
  };
  
  const handleCheckVideo = async () => {
    setLoading(true);
    try {
      const response = await axios.post('http://127.0.0.1:5000/check-video-result', { id: videoId });
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
    <div style={{ padding: "20px" }}>
      <h1>AI Video Generation</h1>

      <div>
        <input
          type="text"
          placeholder="Enter prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          style={{ padding: "10px", width: "80%" }}
        
        />
        <button onClick={handleGenerateVideo} style={{ padding: "10px" }}>Generate Video</button>
      </div>

      {videoId && (
        <div>
          <h3>Video Generation ID: {videoId}</h3>
          <button onClick={handleCheckVideo} style={{ padding: "10px" }}>
            Check Video Result
          </button>
        </div>
      )}

      {loading && <p>Loading...</p>}

      {videoUrl && (
        <div>
          <h3>Your Generated Video:</h3>
          <video width="600" controls>
    
            
            <source src={videoUrl} type="video/mp4" />
            Your browser does not support the video tag.
          </video>
        </div>
      )}
    </div>
  );
}

export default App;
