from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from huggingface_hub import InferenceClient

import re
import requests
import json
import os
import base64
import time

import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image

from agents.segmentation import SEGMENTATION_AGENT
from agents.ocr import OCR_AGENT, pladdleOCR

from utils import *

app = Flask(__name__)

segmentation_agent = SEGMENTATION_AGENT()

HF_API_KEY = os.environ.get("HUGGINGFACE_API_KEY")


def call_qwen_vision_api(img_b64, prompt):
    """
    Make API request to Qwen vision model
    """
    try:
        client = InferenceClient(api_key=HF_API_KEY)
        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-VL-7B-Instruct",
            messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                    }
                ]
            }
            ],
            max_tokens=256,
        )
    
        return response.choices[0].message.content
    
    except requests.exceptions.Timeout:
        raise Exception("API request timed out")
    except requests.exceptions.RequestException as e:
        raise Exception(f"API request failed: {str(e)}")

def call_qwen_vision_api_stream(img_b64, prompt):
    """
    Stream responses from Qwen vision model
    """
    try:
        client = InferenceClient(api_key=HF_API_KEY)
        stream = client.chat.completions.create(
            model="Qwen/Qwen2.5-VL-7B-Instruct",
            messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                    }
                ]
            }
            ],
            max_tokens=512,
            stream=True  # Enable streaming
        )
    
        return stream
    
    except requests.exceptions.Timeout:
        raise Exception("API request timed out")
    except requests.exceptions.RequestException as e:
        raise Exception(f"API request failed: {str(e)}")

def extract_bbox(data):
    match = re.search(r'```json\n(.*?)\n```', data, re.DOTALL)

    if match:
        try:
            json_data = json.loads(match.group(1).strip())

            if isinstance(json_data, list) and json_data and "bbox_2d" in json_data[0]:
                return json_data[0]["bbox_2d"]

            if isinstance(json_data, dict) and "bbox_2d" in json_data:
                return json_data["bbox_2d"]

        except json.JSONDecodeError:
            return None

    return None

def text_to_audio_base64(text):
    """Convert text to base64 audio"""
    from gtts import gTTS
    tts = gTTS(text=text, lang='en', slow=False)
    audio_fp = BytesIO()
    tts.write_to_fp(audio_fp)
    audio_fp.seek(0)
    return base64.b64encode(audio_fp.read()).decode('utf-8')


def convert_to_bytes(image):
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return image_base64

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    try:
        data = request.json["image"]
        image_data = data.split(",")[1]
        binary = base64.b64decode(image_data)
        
        filepath = "photo.jpg"
        with open(filepath, "wb") as f:
            f.write(binary)
        
        return {"status": "ok", "message": "Image saved successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400

@app.route("/speak", methods=["POST"])
def speak():
    """Convert text to speech and return audio"""
    try:
        from gtts import gTTS
        
        data = request.json["image"]
        image_base64 = data.split(",")[1]
        text = call_qwen_vision_api(image_base64, "describe this image in detail")
        
        tts = gTTS(text=text, lang='en', slow=False)
        
        audio_fp = BytesIO()
        tts.write_to_fp(audio_fp)
        audio_fp.seek(0)
        
        audio_base64 = base64.b64encode(audio_fp.read()).decode('utf-8')
        
        return jsonify({
            "status": "success",
            "audio": f"data:audio/mp3;base64,{audio_base64}"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Speech generation failed: {str(e)}"
        }), 500

@app.route("/speak_stream", methods=["POST"])
def speak_stream():
    """Stream audio generation in real-time as text is generated"""
    def generate():
        try:
            data = request.json["image"]
            image_base64 = data.split(",")[1]
            
            # Stream responses from vision API
            stream = call_qwen_vision_api_stream(image_base64, "Describe this image in detail. Use short, clear sentences.")
            
            buffer = ""
            sentence_endings = re.compile(r'[.!?]+')
            
            for chunk in stream:
                # Get the delta content
                if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        text_chunk = delta.content
                        buffer += text_chunk
                        
                        # Check if we have a complete sentence
                        sentences = sentence_endings.split(buffer)
                        
                        # Process complete sentences (all but the last element)
                        for i in range(len(sentences) - 1):
                            sentence = sentences[i].strip()
                            if sentence:
                                # Add back the punctuation
                                sentence += buffer[buffer.find(sentence) + len(sentence)]
                                
                                print(f"Generating audio for: {sentence}")
                                
                                # Generate audio for this sentence
                                try:
                                    audio_base64 = text_to_audio_base64(sentence)
                                    yield f"data: {json.dumps({'audio': audio_base64, 'text': sentence})}\n\n"
                                except Exception as audio_error:
                                    print(f"Audio generation error: {audio_error}")
                                    continue
                        
                        # Keep the incomplete sentence in buffer
                        buffer = sentences[-1] if sentences else ""
            
            # Process any remaining text in buffer
            if buffer.strip():
                print(f"Generating audio for final: {buffer}")
                try:
                    audio_base64 = text_to_audio_base64(buffer.strip())
                    yield f"data: {json.dumps({'audio': audio_base64, 'text': buffer.strip()})}\n\n"
                except Exception as audio_error:
                    print(f"Final audio generation error: {audio_error}")
            
            # Signal completion
            yield f"data: {json.dumps({'done': True})}\n\n"
            
        except Exception as e:
            print(f'Exception: {str(e)}')
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route("/ask_question", methods=["POST"])
def ask_question():
    """Answer a voice question about the image"""
    try:
        from gtts import gTTS
        
        data = request.json["image"]
        question = request.json.get("question", "")
        
        if not question:
            return jsonify({
                "status": "error",
                "message": "No question provided"
            }), 400
        
        image_base64 = data.split(",")[1]
        
        prompt = f"Answer this question about the image: {question}"
        answer = call_qwen_vision_api(image_base64, prompt)
        
        tts = gTTS(text=answer, lang='en', slow=False)
        
        audio_fp = BytesIO()
        tts.write_to_fp(audio_fp)
        audio_fp.seek(0)
        
        audio_base64 = base64.b64encode(audio_fp.read()).decode('utf-8')
        
        return jsonify({
            "status": "success",
            "audio": f"data:audio/mp3;base64,{audio_base64}",
            "answer": answer
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Question processing failed: {str(e)}"
        }), 500

@app.route("/detect_private", methods=["POST"])
def detect_private():
    """Detect private/confidential objects in the image using Qwen Vision API"""
    def generate():
        try:
            data = request.json["image"]
            image_base64 = data.split(",")[1]
            
            # First audio: Starting detection
            try:
                audio = text_to_audio_base64("Scanning for private information")
                yield f"data: {json.dumps({'audio': audio, 'text': 'Scanning for private information', 'stage': 'start'})}\n\n"
            except Exception as e:
                print(f"Audio error: {e}")
            
            prompt = 'Locate paper document in the image, and output in JSON format.'
            detection_result = call_qwen_vision_api(image_base64, prompt)
            bbox_orig = extract_bbox(detection_result)
            
            image_data = base64.b64decode(image_base64)
            image_bytes = BytesIO(image_data)
            image = Image.open(image_bytes)

            cropped_image_base64 = None
            has_private = True
            if bbox_orig is not None:
                # Second audio: Found document
                try:
                    audio = text_to_audio_base64("Private document detected. Analyzing content.")
                    yield f"data: {json.dumps({'audio': audio, 'text': 'Private document detected. Analyzing content.', 'stage': 'detected'})}\n\n"
                except Exception as e:
                    print(f"Audio error: {e}")
                cropped_image = image.crop(bbox_orig)
                
                pred_mask = segmentation_agent.segment_document(cropped_image)
                cropped_image_tmp = set_zero_outside_mask(pil_to_opencv(cropped_image), pred_mask)
                cropped_image_tmp = opencv_to_pil(cropped_image_tmp)
    
                rotate_angle = 90
                rotated_image_v1 = cropped_image_tmp.rotate(rotate_angle, resample=Image.BICUBIC, expand=True, fillcolor=(255,255,255))
                rotated_image_v1.save("rotated_image.jpg")
    
                points, strs, elapse = pladdleOCR()
    
                angles = []
                for pol in points[:10]:
                    angles.append(polygon_orientation(pol))
    
                mean_angle  = np.mean(angles)
                total_angle = rotate_angle
    
                if angles:
                    total_angle += mean_angle
                    rotated_image_v1 = cropped_image_tmp.rotate(total_angle, resample=Image.BICUBIC, expand=True, fillcolor=(255,255,255))
                    rotated_image_v1.save("rotated_image.jpg")
                    points, strs, elapse = pladdleOCR()
    
                image_base64 = convert_to_bytes(rotated_image_v1)            
                prompt = "Locate all text (bbox coordinates). Include all readable and blury text and output in JSON format."
                ocr_result = call_qwen_vision_api(image_base64, prompt)
                data = extract_bbox_removing_incomplete(ocr_result)
    
                hr_im  = image.copy()
    
                meta_categories = ["bank statement", "letter with address", "credit or debit card", "bills or receipt", "preganancy test", "pregnancy test box", "mortage or investment report", "doctor prescription", "empty pill bottle", "condom with plastic bag", "tattoo sleeve", "transcript", "business card", "condom box", "local newspaper", "medical record document", "email", "phone", "id card",]
    
                prompt = f"From this list of categories: {' ,'.join(meta_categories)}, which one is related to this image. Only output the category" 
                image_base64 = convert_to_bytes(hr_im)
                metacategory = call_qwen_vision_api(image_base64, prompt)

                try:
                    audio = text_to_audio_base64(f"I identified a {metacategory}")
                    yield f"data: {json.dumps({'audio': audio, 'text': 'Scanning for private information', 'stage': 'start'})}\n\n"
                except Exception as e:
                    print(f"Audio error: {e}")
            

                texts = [d['text_content']for d in data]
    
                with open(f'label2item_list.json', 'r') as file:
                    unique_categories_per_metacategory = json.load(file)
                unique_categories = unique_categories_per_metacategory[metacategory]["contained_info"]
                unique_categories.append("other")
                unique_categories.append("none")
                
                high_risk = []
                for idx, text in enumerate(texts):
                    # Audio update: Classifying text
                    if idx == 0:  # Only announce once at the start
                        try:
                            audio = text_to_audio_base64(f"Classifying {len(texts)} text regions")
                            yield f"data: {json.dumps({'audio': audio, 'text': f'Classifying {len(texts)} text regions', 'stage': 'classifying'})}\n\n"
                        except Exception as e:
                            print(f"Audio error: {e}")
                    
                    prompt = f"Based on the image, classify this text: '{text} 'using these categories: {unique_categories}. Output only one category."
                    label = call_qwen_vision_api(image_base64, prompt)
                    try:
                        audio = text_to_audio_base64(f"{text} is a {label}")
                        yield f"data: {json.dumps({'audio': audio, 'text': f'{text} is a {label}', 'stage': 'classifying'})}\n\n"
                    except Exception as e:
                        print(f"Audio error: {e}")
                    

                    high_risk.append(label)
    
                crop_x = bbox_orig[0]
                crop_y = bbox_orig[1]
                
                masked_count = 0
                for id_p, bbox_rotated_tmp in enumerate(data):
                  bbox_rotated = bbox_rotated_tmp['bbox_2d']
                  text = bbox_rotated_tmp['text_content']
                  poly_orig = rotated_bbox_polygon(bbox_rotated, -total_angle, cropped_image_tmp.size, rotated_image_v1.size)
                
                  final_poly = []
                  for (x,y) in poly_orig:
                    final_poly.append((crop_x+x, crop_y+y))
                
                  if high_risk[id_p] != 'none' and  high_risk[id_p] != 'other':
                      draw_orig = ImageDraw.Draw(hr_im)
                      draw_orig.polygon(final_poly, fill="black")
                      masked_count += 1
                
                # Final audio: Masking complete
                if masked_count > 0:
                    try:
                        audio = text_to_audio_base64(f"Masked {masked_count} sensitive text region{'s' if masked_count != 1 else ''}. Processing complete.")
                        yield f"data: {json.dumps({'audio': audio, 'text': f'Masked {masked_count} sensitive regions', 'stage': 'complete'})}\n\n"
                    except Exception as e:
                        print(f"Audio error: {e}")
                else:
                    try:
                        audio = text_to_audio_base64("No sensitive information found. Processing complete.")
                        yield f"data: {json.dumps({'audio': audio, 'text': 'No sensitive information found', 'stage': 'complete'})}\n\n"
                    except Exception as e:
                        print(f"Audio error: {e}")
                
                image_base64 = convert_to_bytes(hr_im)
    
            else:
                has_private = False
                # Audio: No private document found
                try:
                    audio = text_to_audio_base64("No private document detected in the image.")
                    yield f"data: {json.dumps({'audio': audio, 'text': 'No private document detected', 'stage': 'none'})}\n\n"
                except Exception as e:
                    print(f"Audio error: {e}")

            
            yield f"data: {json.dumps({'done': True, 'detection': detection_result, 'has_private_info': has_private, 'cropped_image': f'data:image/png;base64,{image_base64}' if image_base64 else None})}\n\n"
            
        except Exception as e:
            print(f'Exception: {str(e)}')
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')
            
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
