import { useState } from "react";
import axios from "axios";
import { 
  PlayIcon, 
  SparklesIcon, 
  BoltIcon,
  CheckIcon,
  StarIcon,
  ChevronRightIcon,
  ClockIcon,
  CpuChipIcon,
  VideoCameraIcon,
  ArrowDownTrayIcon,
  XMarkIcon,
  ArrowPathIcon,
  Cog6ToothIcon
} from "@heroicons/react/24/outline";

export default function AIVideoGeneratorLanding() {
  const [prompt, setPrompt] = useState("");
  const [requestId, setRequestId] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [coverImage, setCoverImage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [showDemo, setShowDemo] = useState(false);
  const [queuePosition, setQueuePosition] = useState(null);
  const [settings, setSettings] = useState({
    model: "cogvideox-2",
    quality: "quality",
    with_audio: true,
    size: "1920x1080",
    fps: 30
  });
  const [showSettings, setShowSettings] = useState(false);

  const generateVideo = async () => {
    try {
      setLoading(true);
      setStatus("Submitting request...");
      setVideoUrl(null);
      setCoverImage(null);
      setQueuePosition(null);

      const response = await axios.post('https://text-to-video-backend1.onrender.com/generate-video', {
        prompt,
        ...settings
      });

      if (response.data.taskId) {
        setQueuePosition(response.data.queuePosition);
        pollForVideo(response.data.taskId);
      } else {
        setStatus("Failed to submit video generation request.");
        setLoading(false);
      }
    } catch (error) {
      console.error("Error generating video:", error);
      setStatus("Failed to submit request. Please try again.");
      setLoading(false);
    }
  };

  const pollForVideo = async (taskId) => {
    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`https://text-to-video-backend1.onrender.com/check-status/${taskId}`);
        const { status, message, videoUrl, coverImageUrl, progress, queue_position } = response.data;

        if (status === "success") {
          setVideoUrl(videoUrl);
          setCoverImage(coverImageUrl);
          setStatus("Video generated successfully!");
          setLoading(false);
          setQueuePosition(null);
          clearInterval(interval);
        } else if (status === "processing") {
          setStatus(`${message || 'Processing video...'} (${progress}%)`);
          setQueuePosition(null);
        } else if (status === "queued") {
          setStatus(message || 'Waiting in queue...');
          setQueuePosition(queue_position);
        } else {
          setStatus(`Error: ${message}`);
          setLoading(false);
          setQueuePosition(null);
          clearInterval(interval);
        }
      } catch (error) {
        console.error("Error checking video status:", error);
        setStatus("Error retrieving video status.");
        setLoading(false);
        setQueuePosition(null);
        clearInterval(interval);
      }
    }, 1000);

    return () => clearInterval(interval);
  };

  const resetGeneration = () => {
    setVideoUrl(null);
    setCoverImage(null);
    setStatus("");
    setLoading(false);
    setRequestId(null);
  };

  const handleSettingsChange = (setting, value) => {
    setSettings(prev => ({
      ...prev,
      [setting]: value
    }));
  };

  const handleDownload = async (url, filename) => {
    try {
      const response = await fetch(url);
      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);
    } catch (error) {
      console.error('Error downloading video:', error);
    }
  };

  const features = [
    {
      icon: BoltIcon,
      title: "Text-to-Video in Seconds",
      description: "Transform any text prompt into stunning videos instantly with our advanced AI technology."
    },
    {
      icon: SparklesIcon,
      title: "100+ AI-Generated Styles",
      description: "Choose from diverse templates and styles - from corporate to social media, animated to cinematic."
    },
    {
      icon: CpuChipIcon,
      title: "Auto Voiceovers & Music",
      description: "AI-powered voice synthesis and background music that perfectly matches your video's mood."
    },
    {
      icon: CheckIcon,
      title: "No Watermarks, Full HD",
      description: "Export professional-quality videos in Full HD without any watermarks or restrictions."
    }
  ];

  const steps = [
    {
      step: "01",
      title: "Describe Your Idea",
      description: "Simply type what you want to create - be as creative or specific as you like."
    },
    {
      step: "02", 
      title: "AI Generates Video Options",
      description: "Our neural network processes your request and creates multiple video variations."
    },
    {
      step: "03",
      title: "Download & Share",
      description: "Choose your favorite, download instantly, and share across all your platforms."
    }
  ];

  const testimonials = [
    {
      name: "Lucky Negi",
      role: "Content Creator",
      image: "/lucky.jpeg",
      text: "This AI video generator has revolutionized my content creation process. What used to take hours now takes minutes!",
      rating: 5,
      videoUrl: "./demo-2.mp4",
      prompt: "A serene mountain landscape with flowing waterfalls and misty forests",
      thumbnail: "./demo-2.mp4"
    },
    {
      name: "Marcus Rodriguez", 
      role: "Marketing Director",
      image: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&h=150&fit=crop&crop=face",
      text: "The quality is incredible. Our social media engagement has increased by 300% since we started using AI-generated videos.",
      rating: 5,
      videoUrl: "./demo-video.mp4",
      prompt: "A futuristic city with neon lights and flying vehicles at night",
      thumbnail: "./demo-video.mp4"
    },
    {
      name: "Emily Johnson",
      role: "Small Business Owner", 
      image: "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=150&h=150&fit=crop&crop=face",
      text: "Finally, professional video content without the professional budget. This tool is a game-changer!",
      rating: 5,
      videoUrl: "./demo-3.mp4",
      prompt: "Modern product showcase with floating elements and dynamic lighting",
      thumbnail: "./demo-3.mp4"
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-blue-950 to-black">
      {/* Navigation */}
      <nav className="relative z-50 px-6 py-4">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-gradient-to-r from-blue-500 to-blue-700 rounded-lg flex items-center justify-center animate-float">
              <VideoCameraIcon className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-white">VideoAI</span>
          </div>
          <div className="hidden md:flex items-center space-x-8">
            <a href="#features" className="text-gray-300 hover:text-white transition-colors">Features</a>
    
  
           
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative px-6 py-20 text-center">
        <div className="max-w-4xl mx-auto">
          {/* Animated background elements */}
          <div className="absolute inset-0 overflow-hidden">
            <div className="absolute -top-40 -right-40 w-80 h-80 bg-blue-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-pulse"></div>
            <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-blue-700 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-pulse delay-1000"></div>
          </div>
          
          <div className="relative z-10">
            <h1 className="text-5xl md:text-7xl font-bold text-white mb-6 leading-tight animate-float">
              Transform Ideas into
              <span className="bg-gradient-to-r from-blue-400 to-blue-600 bg-clip-text text-transparent"> Stunning Videos </span>
              in Seconds
            </h1>
            <p className="text-xl text-gray-300 mb-8 max-w-2xl mx-auto">
              Generate professional-quality videos with just a text prompt. Powered by cutting-edge AI technology. No editing skills needed!
            </p>
            
            {/* Demo Input */}
            <div className="max-w-2xl mx-auto mb-8">
              <div className="relative group">
                <div className="absolute -inset-1 bg-gradient-to-r from-blue-600 to-blue-400 rounded-2xl blur opacity-25 group-hover:opacity-50 transition duration-200"></div>
                <div className="relative">
                  <div className="flex items-center justify-between mb-2">
                    <button
                      onClick={() => setShowSettings(true)}
                      className="flex items-center space-x-2 text-gray-400 hover:text-white transition-colors text-sm"
                    >
                      <Cog6ToothIcon className="w-4 h-4" />
                      <span>Advanced Settings</span>
                    </button>
                    <div className="flex items-center space-x-2 text-sm text-gray-400">
                      <span>Quality: {settings.quality}</span>
                      <span>•</span>
                      <span>{settings.size}</span>
                      <span>•</span>
                      <span>{settings.fps}fps</span>
                    </div>
                  </div>
                  <textarea
                    className="w-full p-6 bg-black/50 backdrop-blur-md border-2 border-blue-500/20 rounded-2xl text-white placeholder-gray-400 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300"
                    rows="3"
                    placeholder="Describe your video idea... (e.g., 'A futuristic cityscape at sunset with flying cars')"
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                  />
                  <button
                    onClick={generateVideo}
                    disabled={loading || !prompt.trim()}
                    className="absolute right-3 bottom-3 bg-gradient-to-r from-blue-600 to-blue-400 text-white px-8 py-3 rounded-xl hover:scale-105 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 flex items-center space-x-2 shadow-lg shadow-blue-500/20 group"
                  >
                    {loading ? (
                      <>
                        <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin"></div>
                        <span className="font-medium">Creating...</span>
                      </>
                    ) : (
                      <>
                        <SparklesIcon className="w-5 h-5 group-hover:animate-pulse" />
                        <span className="font-medium">Generate Video</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
              
              {status && (
                <div className="mt-4 p-4 bg-black/50 backdrop-blur-md rounded-xl border border-blue-500/20">
                  <div className="flex items-center space-x-2">
                    {loading ? (
                      <div className="w-4 h-4 border-2 border-blue-500/20 border-t-blue-500 rounded-full animate-spin"></div>
                    ) : status.toLowerCase().includes('success') ? (
                      <CheckIcon className="w-5 h-5 text-green-500" />
                    ) : status.toLowerCase().includes('fail') || status.toLowerCase().includes('error') ? (
                      <XMarkIcon className="w-5 h-5 text-red-500" />
                    ) : (
                      <ClockIcon className="w-5 h-5 text-blue-500 animate-pulse" />
                    )}
                    <p className="text-gray-300 font-medium">{status}</p>
                  </div>
                  {queuePosition > 0 && (
                    <div className="mt-2 flex items-center space-x-2 text-sm text-gray-400">
                      <span>Queue Position: {queuePosition}</span>
                      <span>•</span>
                      <span>Estimated wait time: {queuePosition * 2} minutes</span>
                    </div>
                  )}
                </div>
              )}

              {/* Quick Prompts */}
              <div className="mt-4 flex flex-wrap gap-2">
                <button 
                  onClick={() => setPrompt("A serene mountain landscape with flowing waterfalls")}
                  className="text-sm px-4 py-2 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 hover:bg-blue-500/20 transition-all"
                >
                  🏔️ Mountain Scene
                </button>
                <button 
                  onClick={() => setPrompt("A futuristic city with neon lights and flying vehicles")}
                  className="text-sm px-4 py-2 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 hover:bg-blue-500/20 transition-all"
                >
                  🌆 Futuristic City
                </button>
                <button 
                  onClick={() => setPrompt("An abstract animation of colorful particles forming a logo")}
                  className="text-sm px-4 py-2 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 hover:bg-blue-500/20 transition-all"
                >
                  ✨ Abstract Logo
                </button>
              </div>
            </div>

            {/* Demo Video Section */}
            <div className="mt-12 max-w-4xl mx-auto">
              <div className="relative group">
                <div className="absolute -inset-1 bg-gradient-to-r from-blue-600 to-blue-400 rounded-2xl blur opacity-25 group-hover:opacity-50 transition duration-200"></div>
                <div className="relative bg-black/50 backdrop-blur-md rounded-2xl border border-blue-500/20 p-6">
                  <h3 className="text-2xl font-semibold text-white mb-4 flex items-center space-x-2">
                    <PlayIcon className="w-6 h-6 text-blue-400" />
                    <span>See AI Video Generation in Action</span>
                  </h3>
                  
                  <div className="aspect-video relative rounded-xl overflow-hidden ring-1 ring-blue-500/20 mb-4">
                    <video 
                      className="w-full h-full object-cover"
                      controls
                      autoPlay
                      muted
                      loop
                      poster="/demo-thumbnail.jpg"
                    >
                      <source src="/demo-video.mp4" type="video/mp4" />
                      Your browser does not support the video tag.
                    </video>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-black/30 p-4 rounded-xl">
                      <h4 className="text-blue-400 font-medium mb-2">Prompt Used</h4>
                      <p className="text-gray-300 text-sm">"A futuristic cityscape at sunset with flying cars and neon lights, cinematic style"</p>
                    </div>
                    <div className="bg-black/30 p-4 rounded-xl">
                      <h4 className="text-blue-400 font-medium mb-2">Generation Time</h4>
                      <p className="text-gray-300 text-sm">Generated in 2 minutes using our optimized AI model</p>
                    </div>
                    <div className="bg-black/30 p-4 rounded-xl">
                      <h4 className="text-blue-400 font-medium mb-2">Quality Settings</h4>
                      <p className="text-gray-300 text-sm">1080p resolution, 30fps, Quality Priority mode</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

           

            {/* Video Result */}
            {videoUrl && (
              <div className="mt-12 max-w-2xl mx-auto">
                <div className="relative group">
                  <div className="absolute -inset-1 bg-gradient-to-r from-blue-600 to-blue-400 rounded-2xl blur opacity-25 group-hover:opacity-50 transition duration-200"></div>
                  <div className="relative bg-black/50 backdrop-blur-md rounded-2xl border border-blue-500/20 p-6">
                    <h3 className="text-xl font-semibold text-white mb-4 flex items-center space-x-2">
                      <VideoCameraIcon className="w-5 h-5 text-blue-400" />
                      <span>Your Generated Video</span>
                    </h3>
                    
                    {coverImage && (
                      <img 
                        src={coverImage} 
                        alt="Video thumbnail" 
                        className="w-full rounded-xl mb-4 ring-1 ring-blue-500/20"
                      />
                    )}
                    
                    <video className="w-full rounded-xl ring-1 ring-blue-500/20" controls>
                      <source src={videoUrl} type="video/mp4" />
                    </video>
                    
                    <div className="mt-4 flex items-center justify-between">
                      <button 
                        onClick={resetGeneration}
                        className="flex items-center space-x-2 text-gray-400 hover:text-white transition-colors"
                      >
                        <ArrowPathIcon className="w-5 h-5" />
                        <span>Generate Another</span>
                      </button>
                      
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="px-6 py-20">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16 animate-float">
            <h2 className="text-4xl font-bold text-white mb-4">Powered by Cutting-Edge AI</h2>
            <p className="text-xl text-gray-300 max-w-2xl mx-auto">
              Experience the future of video creation with features designed for creators, marketers, and businesses.
            </p>
          </div>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((feature, index) => (
              <div key={index} className="bg-black/40 backdrop-blur-md rounded-2xl border border-blue-900/50 p-6 hover:scale-105 transition-all hover:-translate-y-2 duration-300">
                <div className="w-12 h-12 bg-gradient-to-r from-blue-500 to-blue-700 rounded-xl flex items-center justify-center mb-4 animate-float">
                  <feature.icon className="w-6 h-6 text-white" />
                </div>
                <h3 className="text-xl font-semibold text-white mb-3">{feature.title}</h3>
                <p className="text-gray-300">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works Section */}
     

      {/* Testimonials Section */}
      <section className="px-6 py-20">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16 animate-float">
            <h2 className="text-4xl font-bold text-white mb-4">See What Our Users Create</h2>
            <p className="text-xl text-gray-300">Real examples from our amazing community</p>
          </div>
          
          <div className="grid md:grid-cols-3 gap-8">
            {testimonials.map((testimonial, index) => (
              <div key={index} className="bg-black/40 backdrop-blur-md rounded-2xl border border-blue-900/50 p-6 transform transition-all duration-300 hover:translate-y-[-10px]">
                {/* Video Preview */}
                <div className="relative aspect-video mb-6 rounded-xl overflow-hidden group cursor-pointer">
                  <video 
                    className="w-full h-full object-cover"
                    poster={testimonial.thumbnail}
                    muted
                    loop
                    preload="auto"
                    playsInline
                    controls
                  >
                    <source src={testimonial.videoUrl} type="video/mp4" />
                    Your browser does not support the video tag.
                  </video>
                  <div className="absolute bottom-4 right-4 z-10">
                   
                  </div>
                </div>

                {/* Rating */}
                <div className="flex items-center mb-4">
                  {[...Array(testimonial.rating)].map((_, i) => (
                    <StarIcon key={i} className="w-5 h-5 text-yellow-400 fill-current" />
                  ))}
                </div>

                {/* Testimonial */}
                <p className="text-gray-300 mb-6 italic">"{testimonial.text}"</p>
                
                {/* User Info */}
                <div className="flex items-center">
                  <img 
                    src={testimonial.image} 
                    alt={testimonial.name}
                    className="w-12 h-12 rounded-full mr-4 object-cover ring-2 ring-blue-500"
                  />
                  <div>
                    <p className="text-white font-semibold">{testimonial.name}</p>
                    <p className="text-gray-400 text-sm">{testimonial.role}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
     
      {/* Final CTA Section */}
      <section className="px-6 py-20">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-5xl font-bold text-white mb-6 animate-float">Ready to Create Magic?</h2>
          <p className="text-xl text-gray-300 mb-8">
            Join thousands of creators who are already transforming their ideas into stunning videos.
          </p>
          <button className="bg-gradient-to-r from-blue-500 to-blue-700 text-white px-12 py-4 rounded-full text-lg font-semibold hover:scale-105 transition-all animate-float">
            Start Creating for Free – No Credit Card Needed
          </button>
          <p className="text-gray-400 mt-4">Free forever • Upgrade anytime • Cancel anytime</p>
        </div>
      </section>

      {/* Footer */}
      <footer className="px-6 py-12 border-t border-blue-900/50">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-4 gap-8 mb-8">
            <div>
              <div className="flex items-center space-x-2 mb-4">
                <div className="w-8 h-8 bg-gradient-to-r from-blue-500 to-blue-700 rounded-lg flex items-center justify-center">
                  <VideoCameraIcon className="w-5 h-5 text-white" />
                </div>
                <span className="text-xl font-bold text-white">VideoAI</span>
              </div>
              <p className="text-gray-400">Transform ideas into stunning videos with the power of AI.</p>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Product</h4>
              <ul className="space-y-2">
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors">Features</a></li>
              
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors">API</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Support</h4>
              <ul className="space-y-2">
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors">FAQ</a></li>
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors">Contact</a></li>
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors">Help Center</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Company</h4>
              <ul className="space-y-2">
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors">About</a></li>
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors">Blog</a></li>
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors">Careers</a></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-white/10 pt-8 flex flex-col md:flex-row justify-between items-center">
            <p className="text-gray-400">© 2025 VideoAI. All rights reserved.</p>
            <div className="flex space-x-6 mt-4 md:mt-0">
              <a href="#" className="text-gray-400 hover:text-white transition-colors">Privacy Policy</a>
              <a href="#" className="text-gray-400 hover:text-white transition-colors">Terms of Service</a>
            </div>
          </div>
        </div>
      </footer>

      {/* Advanced Settings Modal */}
      {showSettings && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="max-w-md w-full mx-4 bg-black/80 rounded-2xl p-6 border border-blue-500/20">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-semibold text-white">Advanced Settings</h3>
              <button 
                onClick={() => setShowSettings(false)}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <XMarkIcon className="w-6 h-6" />
              </button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="text-gray-300 text-sm">Quality Mode</label>
                <select 
                  value={settings.quality}
                  onChange={(e) => handleSettingsChange('quality', e.target.value)}
                  className="w-full mt-1 bg-black/50 border border-blue-500/20 rounded-lg p-2 text-white focus:outline-none focus:border-blue-500 transition-colors"
                >
                  <option value="quality">Quality Priority</option>
                  <option value="speed">Speed Priority</option>
                </select>
              </div>

              <div>
                <label className="text-gray-300 text-sm">Resolution</label>
                <select 
                  value={settings.size}
                  onChange={(e) => handleSettingsChange('size', e.target.value)}
                  className="w-full mt-1 bg-black/50 border border-blue-500/20 rounded-lg p-2 text-white focus:outline-none focus:border-blue-500 transition-colors"
                >
                  <option value="1920x1080">1080p (1920x1080)</option>
                  <option value="3840x2160">4K (3840x2160)</option>
                </select>
              </div>

              <div>
                <label className="text-gray-300 text-sm">Frame Rate</label>
                <select 
                  value={settings.fps}
                  onChange={(e) => handleSettingsChange('fps', parseInt(e.target.value))}
                  className="w-full mt-1 bg-black/50 border border-blue-500/20 rounded-lg p-2 text-white focus:outline-none focus:border-blue-500 transition-colors"
                >
                  <option value="30">30 FPS</option>
                  <option value="60">60 FPS</option>
                </select>
              </div>

              <div className="flex items-center justify-between">
                <label className="text-gray-300 text-sm">Generate Audio</label>
                <button 
                  onClick={() => handleSettingsChange('with_audio', !settings.with_audio)}
                  className={`relative w-11 h-6 rounded-full transition-colors ${
                    settings.with_audio ? 'bg-blue-500' : 'bg-gray-700'
                  }`}
                >
                  <span className={`absolute w-4 h-4 bg-white rounded-full transition-transform ${
                    settings.with_audio ? 'translate-x-6' : 'translate-x-1'
                  }`} />
                </button>
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setShowSettings(false)}
                className="bg-gradient-to-r from-blue-600 to-blue-400 text-white px-6 py-2 rounded-xl hover:scale-105 transition-all"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
