import React from "react";

const VideoPlayer = ({ source }) => {
  return (
    <div className="video-player mt-6 w-full max-w-xl mx-auto">
      {/* <p className="text-lg mb-4 font-semibold">AI-generated video for: "{prompt}"</p> */}
      
      {/* Video player */}
      <video controls className="w-full h-64 bg-black">
        <source src={source} type="video/mp4" />
        Your browser does not support the video tag.
      </video>
    </div>
  );
};

export default VideoPlayer;
