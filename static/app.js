class sightAI{
    constructor() {
        this.video = document.getElementById("video");
        this.canvas = document.getElementById("canvas");
        this.takePhotoBtn = document.getElementById("takePhoto");
        this.fileInput = document.getElementById("fileInput");
        this.fromFilesBtn = document.getElementById("fromFiles");
        this.maskInfoBtn = document.getElementById("maskInfo");
        this.describeBtn = document.getElementById("describe");
        this.askQuestionBtn = document.getElementById("askQuestion");

        this.currentImageData = null;
        this.recognition = null;
        this.isListening = false;
        this.audioQueue = [];
        this.isPlayingAudio = false;
        this.currentAudio = null;

        this.initializeEvents();
        this.initializeSpeechRecognition();
        this.startCamera();
    }

    async startCamera() {
        try {
            let stream = await navigator.mediaDevices.getUserMedia({ video: true });
            this.video.srcObject = stream;
        } catch (error) {
            console.error("Camera access denied:", error);
            alert("Unable to access camera. Please check permissions.");
        }
    }

    initializeSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        
        if (SpeechRecognition) {
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false;
            this.recognition.interimResults = false;
            this.recognition.lang = 'en-US';
        } else {
            console.warn("Speech recognition not supported in this browser");
        }
    }

    initializeEvents() {
        this.takePhotoBtn.addEventListener("click", () => this.takePhoto());
        this.fromFilesBtn.addEventListener("click", () => this.fileInput.click());
        this.fileInput.addEventListener("change", (event) => this.loadImageFromFile(event));
        this.maskInfoBtn.addEventListener("click", () => this.sendMaskInfo());
        this.describeBtn.addEventListener("click", () => this.describeImageStream());
        this.askQuestionBtn.addEventListener("click", () => this.askQuestion());
    }

    enableActionButtons() {
        this.maskInfoBtn.disabled = false;
        this.describeBtn.disabled = false;
        this.askQuestionBtn.disabled = false;
    }

    displayImageOnCanvas(imageData) {
    const img = new Image();
        img.onload = () => {
            // Use the original image dimensions for better quality
            this.canvas.width = img.width;
            this.canvas.height = img.height;

            const ctx = this.canvas.getContext("2d");

            // Improve rendering quality
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = 'high';

            ctx.drawImage(img, 0, 0);

            this.canvas.style.display = "block";
            this.video.style.display = "none";

            this.currentImageData = imageData;
            this.enableActionButtons();
        };
        img.src = imageData;
    }

    displayImageOnCanvas2(imageData) {
        const img = new Image();
        img.onload = () => {
            this.canvas.width = img.width;
            this.canvas.height = img.height;
            const ctx = this.canvas.getContext("2d");
            ctx.drawImage(img, 0, 0);

            this.canvas.style.display = "block";
            this.video.style.display = "none";

            this.currentImageData = imageData;
            this.enableActionButtons();
        };
        img.src = imageData;
    }

    takePhoto() {
        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;

        let ctx = this.canvas.getContext("2d");
        ctx.drawImage(this.video, 0, 0);

        let imageData = this.canvas.toDataURL("image/png");

        this.displayImageOnCanvas(imageData);
    }

    loadImageFromFile(event) {
        const file = event.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                const imageData = e.target.result;
                this.displayImageOnCanvas(imageData);
            };
            reader.readAsDataURL(file);
        }
    }

    async sendMaskInfo() {
        try {
            this.maskInfoBtn.disabled = true;
            this.maskInfoBtn.textContent = "🔄 Processing...";
            
            this.audioQueue = [];
            this.isPlayingAudio = false;
            if (this.currentAudio) {
                this.currentAudio.pause();
                this.currentAudio = null;
            }

            const finalData = {
                completedAt: new Date().toISOString(),
                image: this.currentImageData
            };

            const response = await fetch('/detect_private', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(finalData)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();

                if (done) {
                    console.log('Detection stream complete');
                    break;
                }

                buffer += decoder.decode(value, { stream: true });
                
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const jsonStr = line.substring(6).trim();
                            if (!jsonStr) continue;
                            
                            const data = JSON.parse(jsonStr);
                            console.log('Received detection data:', data);

                            if (data.error) {
                                console.error('Server error:', data.error);
                                alert(`Error: ${data.error}`);
                                break;
                            }

                            if (data.audio) {
                                console.log('Stage:', data.stage, 'Text:', data.text);
                                this.audioQueue.push(data.audio);

                                if (!this.isPlayingAudio) {
                                    this.playNextAudio();
                                }
                            }

                            if (data.done) {
                                console.log('Detection complete');
                                
                                const checkQueue = setInterval(() => {
                                    if (!this.isPlayingAudio && this.audioQueue.length === 0) {
                                        clearInterval(checkQueue);
                                        
                                        if (data.has_private_info && data.cropped_image) {
                                            this.displayImageOnCanvas(data.cropped_image);
                                        } else {
                                            console.log("No private information detected");
                                        }
                                        
                                        this.maskInfoBtn.disabled = false;
                                        this.maskInfoBtn.textContent = "🛡️ Mask Information";
                                    }
                                }, 100);
                            }
                        } catch (e) {
                            console.error('Error parsing JSON:', e, 'Line:', line);
                        }
                    }
                }
            }

            if (this.isPlayingAudio || this.audioQueue.length > 0) {
                const checkQueue = setInterval(() => {
                    if (!this.isPlayingAudio && this.audioQueue.length === 0) {
                        clearInterval(checkQueue);
                        this.maskInfoBtn.disabled = false;
                        this.maskInfoBtn.textContent = "🛡️ Mask Information";
                    }
                }, 100);
            } else {
                this.maskInfoBtn.disabled = false;
                this.maskInfoBtn.textContent = "🛡️ Mask Information";
            }

        } catch (error) {
            console.error('Error processing the image:', error);
            alert('Error processing the image. Please try again.');
            
            this.maskInfoBtn.disabled = false;
            this.maskInfoBtn.textContent = "🛡️ Mask Information";
        }
    }

    async askQuestion() {
        if (!this.recognition) {
            alert("Speech recognition is not supported in your browser. Please use Chrome or Edge.");
            return;
        }

        try {
            this.askQuestionBtn.disabled = true;
            this.askQuestionBtn.textContent = "🎤 Listening...";
            this.isListening = true;

            this.recognition.start();

            this.recognition.onresult = async (event) => {
                const transcript = event.results[0][0].transcript;
                console.log('Question heard:', transcript);

                this.askQuestionBtn.textContent = "⏳ Processing...";

                const finalData = {
                    completedAt: new Date().toISOString(),
                    image: this.currentImageData,
                    question: transcript
                };

                const response = await fetch('/ask_question', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(finalData)
                });

                const result = await response.json();

                if (result.status === 'success') {
                    const audio = new Audio(result.audio);
                    audio.play();
                    
                    audio.onended = () => {
                        this.askQuestionBtn.disabled = false;
                        this.askQuestionBtn.textContent = "🎤 Ask a Question";
                        this.isListening = false;
                    };
                } else {
                    alert(`Error: ${result.message}`);
                    this.askQuestionBtn.disabled = false;
                    this.askQuestionBtn.textContent = "🎤 Ask a Question";
                    this.isListening = false;
                }
            };

            this.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                alert(`Speech recognition error: ${event.error}`);
                this.askQuestionBtn.disabled = false;
                this.askQuestionBtn.textContent = "🎤 Ask a Question";
                this.isListening = false;
            };

            this.recognition.onend = () => {
                if (this.isListening) {
                    this.askQuestionBtn.disabled = false;
                    this.askQuestionBtn.textContent = "🎤 Ask a Question";
                    this.isListening = false;
                }
            };

        } catch (error) {
            console.error('Error with voice question:', error);
            alert('Error processing voice question. Please try again.');
            this.askQuestionBtn.disabled = false;
            this.askQuestionBtn.textContent = "🎤 Ask a Question";
            this.isListening = false;
        }
    }

    playNextAudio() {
        if (this.audioQueue.length === 0) {
            this.isPlayingAudio = false;
            this.currentAudio = null;
            return;
        }

        this.isPlayingAudio = true;
        const audioData = this.audioQueue.shift();
        
        this.currentAudio = new Audio(`data:audio/mp3;base64,${audioData}`);

        this.currentAudio.onended = () => {
            console.log('Audio chunk finished');
            this.playNextAudio();
        };

        this.currentAudio.onerror = (e) => {
            console.error('Error playing audio chunk:', e);
            this.playNextAudio();
        };

        this.currentAudio.oncanplaythrough = () => {
            console.log('Audio loaded, playing...');
        };

        this.currentAudio.play().catch(err => {
            console.error('Play failed:', err);
            this.playNextAudio();
        });
    }

    async describeImageStream() {
        try {
            if (this.currentAudio) {
                this.currentAudio.pause();
                this.currentAudio = null;
            }

            this.describeBtn.disabled = true;
            this.describeBtn.textContent = "🔊 Speaking...";
            this.audioQueue = [];
            this.isPlayingAudio = false;

            const finalData = {
                completedAt: new Date().toISOString(),
                image: this.currentImageData
            };

            const response = await fetch('/speak_stream', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(finalData)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();

                if (done) {
                    console.log('Stream complete');
                    break;
                }

                buffer += decoder.decode(value, { stream: true });
                
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const jsonStr = line.substring(6).trim();
                            if (!jsonStr) continue;
                            
                            const data = JSON.parse(jsonStr);
                            console.log('Received data:', data);

                            if (data.error) {
                                console.error('Server error:', data.error);
                                alert(`Error: ${data.error}`);
                                break;
                            }

                            if (data.done) {
                                console.log('Received done signal');
                                const checkQueue = setInterval(() => {
                                    if (!this.isPlayingAudio && this.audioQueue.length === 0) {
                                        clearInterval(checkQueue);
                                        this.describeBtn.disabled = false;
                                        this.describeBtn.textContent = "🗣️ Describe Picture";
                                    }
                                }, 100);
                            } else if (data.audio) {
                                console.log('Adding audio to queue, text:', data.text);
                                this.audioQueue.push(data.audio);

                                if (!this.isPlayingAudio) {
                                    this.playNextAudio();
                                }
                            }
                        } catch (e) {
                            console.error('Error parsing JSON:', e, 'Line:', line);
                        }
                    }
                }
            }

            if (this.isPlayingAudio || this.audioQueue.length > 0) {
                const checkQueue = setInterval(() => {
                    if (!this.isPlayingAudio && this.audioQueue.length === 0) {
                        clearInterval(checkQueue);
                        this.describeBtn.disabled = false;
                        this.describeBtn.textContent = "🗣️ Describe Picture";
                    }
                }, 100);
            } else {
                this.describeBtn.disabled = false;
                this.describeBtn.textContent = "🗣️ Describe Picture";
            }

        } catch (error) {
            console.error('Error generating speech:', error);
            alert('Error generating speech. Please try again.');
            this.describeBtn.disabled = false;
            this.describeBtn.textContent = "🗣️ Describe Picture";
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new sightAI();
});
