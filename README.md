# Accessible Camera App - Documentation (CSE518-HCI-Project)

## Installation

1. Create a conda enviorenment

```
conda create --name py10-cse518 python=3.10
conda activate py10-cse518
```

2. Install the following package

```
pip install torch==2.5.1 torchvision==0.20.1 transformers==4.51.3 accelerate
python -m pip install paddlepaddle==3.0.0rc1 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
```

3. Install the requirements.txt

```
pip install -r requirements.txt
```

4. Download external models (PaddleOCR)
   
```
wget https://paddleocr.bj.bcebos.com/dygraph_v2.0/pgnet/e2e_server_pgnetA_infer.tar && tar xf e2e_server_pgnetA_infer.tar
```

5. Add a huggingface token
   
```
huggingface-cli login
```

6. Install ffmpeg
```
 sudo apt-get install ffmpeg
```

---

## Overview

An accessible web MULTI-AGENT application designed for visually impaired users to interact with images through voice commands and audio feedback. The app provides image description, voice Q&A, and intelligent privacy masking for sensitive documents.

---

## Project Structure

```
accessible-camera-app/
│
├── app.py                      # Flask backend server
├── templates/
│   └── index.html             # Main web interface
├── static/
│   └── app.js                 # Frontend JavaScript logic
├── agents/
│   ├── ocr.py                 # OCR agent (PaddleOCR integration)
│   ├── vlm.py                 # Vision Language Model functions
│   └── segmentation.py        # Image segmentation utilities
├── utils.py                   # Helper functions
├── label2item_list.json       # Document category mappings
└── requirements.txt           # Python dependencies
```

---

## Core Features

### 1. **Image Description** 🗣️
- Captures or uploads image
- Generates natural language description using AI
- Converts description to speech
- Streams audio in real-time as sentences are generated

### 2. **Voice Q&A** 🎤
- Records user's voice question about the image
- Transcribes speech to text
- Queries AI vision model for answer
- Returns spoken audio response

### 3. **Privacy Masking** 🛡️
- Detects documents in images (bank statements, medical records, IDs, etc.)
- Extracts and classifies text fields (names, addresses, account numbers, etc.)
- Interactive voice-guided masking workflow
- Option for automatic or custom field masking
- Returns image with sensitive information blacked out

---

## Technology Stack

### Backend
- **Flask** - Web framework
- **PaddleOCR** - Text detection and recognition
- **Qwen Vision API** - Image understanding and VLM
- **gTTS** - Google Text-to-Speech
- **SpeechRecognition** - Audio transcription
- **PIL/OpenCV** - Image processing

### Frontend
- **Vanilla JavaScript** - No frameworks
- **MediaRecorder API** - Audio recording
- **Fetch API** - Server communication
- **HTML5 Canvas** - Image display
- **Web Audio API** - Audio playback

---

## Privacy Masking Workflow

```
1. Document Detection
   └─> Locate paper document in image
   
2. Document Extraction & Preprocessing
   └─> Crop, mask, and rotate document
   
3. OCR & Text Extraction
   └─> Extract all text regions with coordinates
   
4. Document Classification
   └─> Identify document type (bank statement, medical record, etc.)
   
5. Field Classification
   └─> Classify each text field (name, address, account #, etc.)
   
6. Interactive Masking
   ├─> User Prompt: "Do you want regular masking?"
   │   ├─> YES: Mask all sensitive fields
   │   └─> If "YES" is not detected: "Which fields do you want to mask?"
   │       └─> User specifies fields by voice
   
7. Apply Masking
   └─> Black out selected regions in original image
   
8. Return Result
   └─> Masked image displayed to user
```

---

## Accessibility Features

1. **Audio Feedback**: Every action provides spoken status updates
2. **Keyboard Navigation**: All buttons are keyboard accessible
3. **Screen Reader Support**: ARIA labels on all interactive elements
4. **High Contrast**: Simple, clear visual design
5. **Mobile Optimized**: Responsive layout for phones

---

## Live Demo

Application is more stabled in localhost, but I create a live demo for a limited time to hold user studies at: [cse-project](https://116632931-sbuproject.com/)

---
