/**
 * sightAI - Accessible Camera Application for Visually Impaired Users
 */
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
        this.audioQueue = [];
        this.isPlayingAudio = false;
        this.currentAudio = null;
        
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.recordingStream = null;

        this.initializeEvents();
        this.startCamera();
    }

    /**
     * Initializes camera stream with back camera as default on mobile. Falls back to front camera if unavailable.
     */
    async startCamera() {
        try {
            let stream = await navigator.mediaDevices.getUserMedia({ 
                video: {
                    facingMode: { ideal: 'environment' }  // 'environment' = back camera
                } 
            });
            this.video.srcObject = stream;
        } catch (error) {
            console.error("Camera access denied:", error);
            alert("Unable to access camera. Please check permissions.");
        }
    }
    
    /**
     * Attaches event listeners to all UI buttons. Sets up click handlers for interactions.
     */
    initializeEvents() {
        this.takePhotoBtn.addEventListener("click", () => this.takePhoto());
        this.fromFilesBtn.addEventListener("click", () => this.fileInput.click());
        this.fileInput.addEventListener("change", (event) => this.loadImageFromFile(event));
        this.maskInfoBtn.addEventListener("click", () => this.sendMaskInfo());
        this.describeBtn.addEventListener("click", () => this.describeImageStream());
        this.askQuestionBtn.addEventListener("click", () => this.askQuestion());
    }

    /**
     * Enables all action buttons after image is captured or loaded. Buttons are disabled by default.
     */
    enableActionButtons() {
        this.maskInfoBtn.disabled = false;
        this.describeBtn.disabled = false;
        this.askQuestionBtn.disabled = false;
    }

    /**
     * Displays image on canvas and hides video stream. Stores current image data and enables action buttons.
     */
    displayImageOnCanvas(imageData) {
        const img = new Image();
        img.onload = () => {
            this.canvas.width = img.width;
            this.canvas.height = img.height;

            const ctx = this.canvas.getContext("2d");
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

    /**
     * Captures photo from video stream and displays it. Takes snapshot of current video frame.
     */
    takePhoto() {
        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;

        let ctx = this.canvas.getContext("2d");
        ctx.drawImage(this.video, 0, 0);

        let imageData = this.canvas.toDataURL("image/png");
        this.displayImageOnCanvas(imageData);
    }

    /**
     * Captures photo from video stream and displays it. Takes snapshot of current video frame.
     */
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

    /**
     * Records audio using MediaRecorder API with configurable duration. Returns promise that resolves with audio blob.
     */	
    async recordAudio(maxDuration = 10000) {
        return new Promise(async (resolve, reject) => {
            try {
                this.recordingStream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true
                    } 
                });

                this.audioChunks = [];
                
                let mimeType = 'audio/webm';
                if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
                    mimeType = 'audio/webm;codecs=opus';
                } else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
                    mimeType = 'audio/ogg;codecs=opus';
                } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
                    mimeType = 'audio/mp4';
                } else if (MediaRecorder.isTypeSupported('audio/wav')) {
                    mimeType = 'audio/wav';
                }

                this.mediaRecorder = new MediaRecorder(this.recordingStream, { mimeType });
                
                this.mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        this.audioChunks.push(event.data);
                    }
                };

                this.mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(this.audioChunks, { type: mimeType });
                    
                    // Stop all tracks
                    if (this.recordingStream) {
                        this.recordingStream.getTracks().forEach(track => track.stop());
                        this.recordingStream = null;
                    }
                    
                    resolve(audioBlob);
                };

                this.mediaRecorder.onerror = (event) => {
                    if (this.recordingStream) {
                        this.recordingStream.getTracks().forEach(track => track.stop());
                        this.recordingStream = null;
                    }
                    reject(new Error('Recording failed: ' + event.error));
                };

                this.mediaRecorder.start();
                this.isRecording = true;

                setTimeout(() => {
                    if (this.isRecording && this.mediaRecorder && this.mediaRecorder.state === 'recording') {
                        this.stopRecording();
                    }
                }, maxDuration);

            } catch (error) {
                reject(error);
            }
        });
    }

    /**
     * Stops the current audio recording. Sets recording flag to false and stops MediaRecorder.
     */	
    stopRecording() {
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.isRecording = false;
            this.mediaRecorder.stop();
        }
    }

    /**
     * Stops the current audio recording. Sets recording flag to false and stops MediaRecorder.
     */
    showRecordingModal() {
        return new Promise((resolve, reject) => {
            const overlay = document.createElement('div');
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.8);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
                padding: 20px;
            `;

            const modal = document.createElement('div');
            modal.style.cssText = `
                background: white;
                padding: 40px;
                border-radius: 12px;
                max-width: 400px;
                width: 100%;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
                text-align: center;
            `;

            modal.innerHTML = `
                <div style="margin-bottom: 20px;">
                    <div id="recordingIndicator" style="
                        width: 80px;
                        height: 80px;
                        background: #dc3545;
                        border-radius: 50%;
                        margin: 0 auto 20px;
                        animation: pulse 1.5s ease-in-out infinite;
                    "></div>
                    <style>
                        @keyframes pulse {
                            0%, 100% { transform: scale(1); opacity: 1; }
                            50% { transform: scale(1.1); opacity: 0.8; }
                        }
                    </style>
                </div>
                <h2 style="margin: 0 0 10px 0; color: #2d6cdf; font-size: 22px;">🎤 Recording...</h2>
                <p style="margin: 0 0 20px 0; color: #666; font-size: 16px;">
                    Ask your question about the image
                </p>
                <p id="timer" style="margin: 0 0 25px 0; color: #999; font-size: 14px;">
                    Time: 0s / 10s
                </p>
                <button 
                    id="stopRecording"
                    style="
                        padding: 14px 32px;
                        font-size: 16px;
                        background: #dc3545;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        cursor: pointer;
                        font-weight: 600;
                        width: 100%;
                    "
                >Stop & Submit</button>
            `;

            overlay.appendChild(modal);
            document.body.appendChild(overlay);

            const stopBtn = modal.querySelector('#stopRecording');
            const timer = modal.querySelector('#timer');
            
            let startTime = Date.now();
            const timerInterval = setInterval(() => {
                const elapsed = Math.floor((Date.now() - startTime) / 1000);
                timer.textContent = `Time: ${elapsed}s / 10s`;
            }, 100);

            let audioPromise = null;

            const cleanup = () => {
                clearInterval(timerInterval);
                if (overlay.parentNode) {
                    document.body.removeChild(overlay);
                }
            };

            audioPromise = this.recordAudio(10000);

            stopBtn.addEventListener('click', () => {
                this.stopRecording();
                
                audioPromise.then(audioBlob => {
                    cleanup();
                    resolve(audioBlob);
                }).catch(err => {
                    cleanup();
                    reject(err);
                });
            });

            audioPromise.then(audioBlob => {
                if (overlay.parentNode) {
                    cleanup();
                    resolve(audioBlob);
                }
            }).catch(err => {
                cleanup();
                reject(err);
            });
        });
    }

    /**
     * Transcribes audio blob to text using backend service. Sends audio file to /transcribe_audio endpoint.
     */
    async transcribeAudio(audioBlob) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        
        if (SpeechRecognition) {
            try {
                console.log('Using fallback transcription method');
            } catch (e) {
                console.log('Web Speech API failed, using backend');
            }
        }

        return await this.transcribeAudioBackend(audioBlob);
    }

    /**
     * Sends audio to backend transcription service. Posts audio file to server and returns transcribed text.
     */
    async transcribeAudioBackend(audioBlob) {
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');

        const response = await fetch('/transcribe_audio', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`Transcription failed: ${response.status}`);
        }

        const result = await response.json();
        
        if (result.status === 'success') {
            return result.text;
        } else {
            throw new Error(result.message || 'Transcription failed');
        }
    }

    /**
     * Records voice question, transcribes it, and gets audio answer. Handles entire voice Q&A workflow.
     */
    async askQuestion() {
        if (!this.currentImageData) {
            alert("Please take or select an image first.");
            return;
        }

        try {
            this.askQuestionBtn.disabled = true;
            this.askQuestionBtn.textContent = "🎤 Starting...";

            try {
                await navigator.mediaDevices.getUserMedia({ audio: true })
                    .then(stream => stream.getTracks().forEach(track => track.stop()));
            } catch (error) {
                alert("Microphone access denied. Please enable microphone permissions and try again.");
                this.askQuestionBtn.disabled = false;
                this.askQuestionBtn.textContent = "🎤 Ask Question";
                return;
            }

            const audioBlob = await this.showRecordingModal();
            
            this.askQuestionBtn.textContent = "⏳ Transcribing...";
            
            const question = await this.transcribeAudio(audioBlob);
            
            if (!question || question.trim() === '') {
                throw new Error('Could not understand the question. Please try again.');
            }

            console.log('Transcribed question:', question);
            
            this.askQuestionBtn.textContent = "⏳ Processing...";
            await this.processQuestion(question.trim());

        } catch (error) {
            await this.processQuestion("Error with voice question");
	    console.error('Error with voice question:', error);
        } finally {
            this.askQuestionBtn.disabled = false;
            this.askQuestionBtn.textContent = "🎤 Ask Question";
        }
    }

    /**
     * Sends question to backend and plays audio answer. Posts question and image to /ask_question endpoint.
     */
    async processQuestion(question) {
        const finalData = {
            completedAt: new Date().toISOString(),
            image: this.currentImageData,
            question: question
        };

        const response = await fetch('/ask_question', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(finalData)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();

        if (result.status === 'success') {
            console.log('Answer:', result.answer);
            
            const audio = new Audio(result.audio);
            
            return new Promise((resolve, reject) => {
                audio.onended = () => {
                    console.log('Audio answer completed');
                    resolve();
                };

                audio.onerror = (e) => {
                    console.error('Audio playback error:', e);
                    reject(new Error('Audio playback failed'));
                };

                audio.play().catch(err => {
                    console.error('Play failed:', err);
                    reject(err);
                });
            });
        } else {
            throw new Error(result.message || 'Unknown error');
        }
    }


    /**
     * Initiates privacy detection and masking workflow. Starts multi-stage detection pipeline with interactive prompts.
     */
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
    
            await this.callDetectPrivate(null, null, null);
    
        } catch (error) {
            console.error('Error processing the image:', error);
            alert('Error processing the image. Please try again.');
            
            this.maskInfoBtn.disabled = false;
            this.maskInfoBtn.textContent = "🛡️ Mask Information";
        }
    }
    
    /**
     * Calls privacy detection endpoint with user responses and session management. Handles streaming updates and user prompts.
     */
    async callDetectPrivate(userResponse, customFields, sessionId) {
        try {
            const finalData = {
                completedAt: new Date().toISOString(),
                image: this.currentImageData,
                user_response: userResponse,
                custom_fields: customFields,
                session_id: sessionId
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
            let receivedSessionId = sessionId;
    
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
    
                            if (data.error) {
                                console.error('Server error:', data.error);
                                alert(`Error: ${data.error}`);
                                this.maskInfoBtn.disabled = false;
                                this.maskInfoBtn.textContent = "🛡️ Mask Information";
                                return;
                            }
    
                            if (data.audio) {
                                this.audioQueue.push(data.audio);
                                if (!this.isPlayingAudio) {
                                    this.playNextAudio();
                                }
                            }
    
                            if (data.session_id) {
                                receivedSessionId = data.session_id;
                                console.log('Received session ID:', receivedSessionId);
                            }
                            if (data.request_user_input) {
                                await this.waitForAudioQueue();
                                
                                const userVoiceResponse = await this.getUserVoiceResponse();
                                
                                if (userVoiceResponse === 'yes') {
                                    await this.callDetectPrivate('yes', null, receivedSessionId);
                                } else {
                                    await this.callDetectPrivate('no', null, receivedSessionId);
                                }
                                return;
                            }
    
                            if (data.request_custom_fields) {
                                await this.waitForAudioQueue();
                                
                                const customFieldsResponse = await this.getCustomFieldsResponse();
                                
                                await this.callDetectPrivate('no', customFieldsResponse, receivedSessionId);
                                return;
                            }
    
                            if (data.done) {
                                const checkQueue = setInterval(() => {
                                    if (!this.isPlayingAudio && this.audioQueue.length === 0) {
                                        clearInterval(checkQueue);
                                        
                                        if (data.has_private_info && data.cropped_image) {
                                            this.displayImageOnCanvas(data.cropped_image);
                                        }
                                        
                                        this.maskInfoBtn.disabled = false;
                                        this.maskInfoBtn.textContent = "🛡️ Mask Information";
                                    }
                                }, 100);
                            }
                        } catch (e) {
                            console.error('Error parsing JSON:', e);
                        }
                    }
                }
            }
    
        } catch (error) {
            throw error;
        }
    }
    
    /**
     * Calls privacy detection endpoint with user responses and session management. Handles streaming updates and user prompts.
     */
    async waitForAudioQueue() {
        return new Promise((resolve) => {
            const checkInterval = setInterval(() => {
                if (!this.isPlayingAudio && this.audioQueue.length === 0) {
                    clearInterval(checkInterval);
                    resolve();
                }
            }, 100);
        });
    }
    
    /**
     * Records and transcribes user's yes/no response. Returns 'yes' or 'no' based on transcription.
     */
    async getUserVoiceResponse() {
        try {
            const audioBlob = await this.showRecordingModal();
            
            const response = await this.transcribeAudio(audioBlob);
            
            console.log('User voice response:', response);
            
            const lowerResponse = response.toLowerCase().trim();
            if (lowerResponse.includes('yes') || 
                lowerResponse.includes('yeah') || 
                lowerResponse.includes('yep') || 
                lowerResponse.includes('sure') ||
                lowerResponse.includes('okay') ||
                lowerResponse.includes('ok')) {
                return 'yes';
            } else {
                return 'no';
            }
        } catch (error) {
            console.error('Error getting voice response:', error);
            return 'no';
        }
    }
    
    /**
     * Records and transcribes custom field names from user. Returns transcribed field names.
     */
    async getCustomFieldsResponse() {
        try {
            const audioBlob = await this.showRecordingModal();
            const response = await this.transcribeAudio(audioBlob);
            
            console.log('Custom fields response:', response);
            
            return response;
            
        } catch (error) {
            console.error('Error getting custom fields:', error);
            return '';
        }
    }

    /**
     * Plays next audio chunk from queue. Recursively continues until queue is empty.
     */
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
            this.playNextAudio();
        };

        this.currentAudio.onerror = (e) => {
            console.error('Error playing audio chunk:', e);
            this.playNextAudio();
        };

        this.currentAudio.play().catch(err => {
            console.error('Play failed:', err);
            this.playNextAudio();
        });
    }

    /**
     * Streams image description as real-time audio chunks. Receives streaming response and plays audio progressively.
     */
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

                            if (data.error) {
                                console.error('Server error:', data.error);
                                alert(`Error: ${data.error}`);
                                break;
                            }

                            if (data.done) {
                                const checkQueue = setInterval(() => {
                                    if (!this.isPlayingAudio && this.audioQueue.length === 0) {
                                        clearInterval(checkQueue);
                                        this.describeBtn.disabled = false;
                                        this.describeBtn.textContent = "🗣️ Describe Picture";
                                    }
                                }, 100);
                            } else if (data.audio) {
                                this.audioQueue.push(data.audio);
                                if (!this.isPlayingAudio) {
                                    this.playNextAudio();
                                }
                            }
                        } catch (e) {
                            console.error('Error parsing JSON:', e);
                        }
                    }
                }
            }

        } catch (error) {
            this.describeBtn.disabled = false;
            this.describeBtn.textContent = "🗣️ Describe Picture";
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new sightAI();
});
