from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from gradio_client import Client, handle_file

import re
import requests
import json
import os
import base64
import time

import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image

from agents.ocr import OCR_AGENT, pladdleOCR
from agents.vlm import *
from agents.segmentation import *

from utils import *

from werkzeug.middleware.proxy_fix import ProxyFix




app = Flask(__name__)

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

import speech_recognition as sr
from pydub import AudioSegment
import tempfile

import subprocess

@app.route("/debug/ffmpeg")
def debug_ffmpeg():
    out = subprocess.check_output(["ffmpeg", "-version"]).decode()
    return f"<pre>{out}</pre>"

@app.route("/transcribe_audio", methods=["POST"])
def transcribe_audio():
    """
    Transcribe audio file to text using speech recognition.
    Works with multiple audio formats (webm, ogg, mp4, wav).
    """
    try:
        if 'audio' not in request.files:
            return jsonify({
                "status": "error",
                "message": "No audio file provided"
            }), 400

        audio_file = request.files['audio']

        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as temp_audio:
            audio_file.save(temp_audio.name)
            temp_audio_path = temp_audio.name

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
            temp_wav_path = temp_wav.name

        try:
            audio = AudioSegment.from_file(temp_audio_path)
            audio.export(temp_wav_path, format='wav')
        except Exception as e:
            print(f"Audio conversion warning: {e}")
            temp_wav_path = temp_audio_path

        recognizer = sr.Recognizer()

        with sr.AudioFile(temp_wav_path) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio_data = recognizer.record(source)

            try:
                text = recognizer.recognize_google(audio_data)

                try:
                    os.unlink(temp_audio_path)
                    if temp_wav_path != temp_audio_path:
                        os.unlink(temp_wav_path)
                except:
                    pass

                return jsonify({
                    "status": "success",
                    "text": text
                })

            except sr.UnknownValueError:
                return jsonify({
                    "status": "error",
                    "message": "Could not understand the audio. Please speak clearly and try again."
                }), 400

            except sr.RequestError as e:
                try:
                    text = recognizer.recognize_sphinx(audio_data)
                    return jsonify({
                        "status": "success",
                        "text": text
                    })
                except:
                    return jsonify({
                        "status": "error",
                        "message": f"Speech recognition service unavailable: {str(e)}"
                    }), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"Transcription failed: {str(e)}"
        }), 500

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

@app.route("/health")
def health():
    return "OK", 200

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
    def generate():
        try:
            data = request.json["image"]
            image_base64 = data.split(",")[1]
            
            stream = call_qwen_vision_api_stream(image_base64, "Describe this image in detail. Use short, clear sentences.")
            
            buffer = ""
            sentence_endings = re.compile(r'[.!?]+')
            
            for chunk in stream:
                if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        text_chunk = delta.content
                        buffer += text_chunk
                        
                        sentences = sentence_endings.split(buffer)
                        
                        for i in range(len(sentences) - 1):
                            sentence = sentences[i].strip()
                            if sentence:
                                sentence += buffer[buffer.find(sentence) + len(sentence)]
                                
                                print(f"Generating audio for: {sentence}")
                                
                                try:
                                    audio_base64 = text_to_audio_base64(sentence)
                                    yield f"data: {json.dumps({'audio': audio_base64, 'text': sentence})}\n\n"
                                except Exception as audio_error:
                                    print(f"Audio generation error: {audio_error}")
                                    continue
                        
                        buffer = sentences[-1] if sentences else ""
            
            if buffer.strip():
                print(f"Generating audio for final: {buffer}")
                try:
                    audio_base64 = text_to_audio_base64(buffer.strip())
                    yield f"data: {json.dumps({'audio': audio_base64, 'text': buffer.strip()})}\n\n"
                except Exception as audio_error:
                    print(f"Final audio generation error: {audio_error}")
            
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

        if question == "Error with voice question":
            answer = f"I did not understand the question. Can you repeat it"

        else:
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

detection_cache = {}
@app.route("/detect_private", methods=["POST"])
def detect_private():
    """Detect private/confidential objects in the image using Qwen Vision API"""
    def generate():
        try:
            data = request.json["image"]
            user_response = request.json.get("user_response", None)
            custom_fields = request.json.get("custom_fields", None)
            session_id = request.json.get("session_id", None)
            image_base64 = data.split(",")[1]
            
            cached_data = None
            if session_id and session_id in detection_cache:
                cached_data = detection_cache[session_id]
                print(f"Using cached data for session {session_id}")
            
            if cached_data and user_response is not None:
                print("Skipping detection, using cached results")
                image = cached_data['image']
                hr_im = cached_data['hr_im']
                field_info = cached_data['field_info']
                bbox_orig = cached_data['bbox_orig']
                crop_x = cached_data['crop_x']
                crop_y = cached_data['crop_y']
                total_angle = cached_data['total_angle']
                cropped_image_tmp = cached_data['cropped_image_tmp']
                rotated_image_v1 = cached_data['rotated_image_v1']
                
                fields_to_mask_indices = []
                
                if 'yes' in user_response.lower():
                    fields_to_mask_indices = [f['index'] for f in field_info if f['label'] not in ['none', 'other']]
                    try:
                        audio = text_to_audio_base64("Proceeding with regular masking of all sensitive fields")
                        yield f"data: {json.dumps({'audio': audio, 'text': 'Masking all sensitive fields', 'stage': 'masking'})}\n\n"
                    except Exception as e:
                        print(f"Audio error: {e}")
                else:
                    if custom_fields is None:
                        sensitive_fields = [f for f in field_info if f['label'] not in ['none', 'other']]
                        try:
                            field_names = ', '.join([f['label'] for f in sensitive_fields])
                            audio = text_to_audio_base64(f"I found these sensitive fields: {field_names}. Which fields do you want to mask? Please name them.")
                            yield f"data: {json.dumps({'audio': audio, 'text': 'Awaiting custom fields', 'stage': 'awaiting_custom_fields', 'request_custom_fields': True})}\n\n"
                        except Exception as e:
                            print(f"Audio error: {e}")
                        return
                    
                    try:
                        audio = text_to_audio_base64("Masking specified fields")
                        yield f"data: {json.dumps({'audio': audio, 'text': 'Masking custom fields', 'stage': 'masking'})}\n\n"
                    except Exception as e:
                        print(f"Audio error: {e}")
                    
                    for field in field_info:
                        if field['label'] not in ['none', 'other']:
                            if (field['label'].lower() in custom_fields.lower() or 
                                field['text'].lower() in custom_fields.lower()):
                                fields_to_mask_indices.append(field['index'])
                
                hr_im_copy = hr_im.copy()
                masked_count = 0
                for field in field_info:
                    if field['index'] in fields_to_mask_indices:
                        bbox_rotated = field['bbox_2d']
                        
                        poly_orig = rotated_bbox_polygon(bbox_rotated, -total_angle, cropped_image_tmp.size, rotated_image_v1.size)
                        
                        final_poly = []
                        for (x, y) in poly_orig:
                            final_poly.append((crop_x + x, crop_y + y))
                        
                        draw_orig = ImageDraw.Draw(hr_im_copy)
                        draw_orig.polygon(final_poly, fill="black")
                        masked_count += 1
                
                if masked_count > 0:
                    try:
                        audio = text_to_audio_base64(f"Masked {masked_count} sensitive text region{'s' if masked_count != 1 else ''}. Processing complete.")
                        yield f"data: {json.dumps({'audio': audio, 'text': f'Masked {masked_count} sensitive regions', 'stage': 'complete'})}\n\n"
                    except Exception as e:
                        print(f"Audio error: {e}")
                else:
                    try:
                        audio = text_to_audio_base64("No sensitive information was masked. Processing complete.")
                        yield f"data: {json.dumps({'audio': audio, 'text': 'No sensitive information masked', 'stage': 'complete'})}\n\n"
                    except Exception as e:
                        print(f"Audio error: {e}")
                
                if session_id and session_id in detection_cache:
                    del detection_cache[session_id]
                
                image_base64_result = convert_to_bytes(hr_im_copy)
                yield f"data: {json.dumps({'done': True, 'has_private_info': True, 'cropped_image': f'data:image/png;base64,{image_base64_result}'})}\n\n"
                return
            
            print("Running full detection pipeline")
            
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

            has_private = True
            if bbox_orig is not None:
                try:
                    audio = text_to_audio_base64("Private document detected. Analyzing content.")
                    yield f"data: {json.dumps({'audio': audio, 'text': 'Private document detected. Analyzing content.', 'stage': 'detected'})}\n\n"
                except Exception as e:
                    print(f"Audio error: {e}")
                
                cropped_image = image.crop(bbox_orig)

                if cropped_image.mode == "RGBA":
                    cropped_image = cropped_image.convert("RGB")

                cropped_image.save("cropped_image.jpg")

                pred_mask = get_mask()
                cropped_image_tmp = set_zero_outside_mask(pil_to_opencv(cropped_image), pred_mask)
                cropped_image_tmp = opencv_to_pil(cropped_image_tmp)

    
                rotate_angle = 90
                rotated_image_v1 = cropped_image_tmp.rotate(rotate_angle, resample=Image.BICUBIC, expand=True, fillcolor=(255,255,255))
                rotated_image_v1.save("rotated_image.jpg")


                if rotated_image_v1.mode == "RGBA":
                    rotated_image_v1 = rotated_image_v1.convert("RGB")
    
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

                    if rotated_image_v1.mode == "RGBA":
                        rotated_image_v1 = rotated_image_v1.convert("RGB")

                    points, strs, elapse = pladdleOCR()
    
                image_base64_rotated = convert_to_bytes(rotated_image_v1)            
                prompt = "Locate all text (bbox coordinates). Include all readable and blury text and output in JSON format."
                ocr_result = call_qwen_vision_api(image_base64_rotated, prompt)
                data_extracted = extract_bbox_removing_incomplete(ocr_result)
    
                hr_im  = image.copy()
    
                meta_categories = ["bank statement", "letter with address", "credit or debit card", "bills or receipt", "preganancy test", "pregnancy test box", "mortage or investment report", "doctor prescription", "empty pill bottle", "condom with plastic bag", "tattoo sleeve", "transcript", "business card", "condom box", "local newspaper", "medical record document", "email", "phone", "id card",]
    
                prompt = f"From this list of categories: {' ,'.join(meta_categories)}, which one is related to this image. Only output the category" 
                image_base64_full = convert_to_bytes(hr_im)
                metacategory = call_qwen_vision_api(image_base64_full, prompt)

                try:
                    audio = text_to_audio_base64(f"I identified a {metacategory}")
                    yield f"data: {json.dumps({'audio': audio, 'text': f'I identified a {metacategory}', 'stage': 'identified'})}\n\n"
                except Exception as e:
                    print(f"Audio error: {e}")
            
                texts = [d['text_content'] for d in data_extracted]
    
                with open(f'label2item_list.json', 'r') as file:
                    unique_categories_per_metacategory = json.load(file)
                unique_categories = unique_categories_per_metacategory[metacategory]["contained_info"]
                unique_categories.append("other")
                unique_categories.append("none")
                
                high_risk = []
                field_info = []
                for idx, text in enumerate(texts):
                    if idx == 0:
                        try:
                            audio = text_to_audio_base64(f"Classifying {len(texts)} text regions")
                            yield f"data: {json.dumps({'audio': audio, 'text': f'Classifying {len(texts)} text regions', 'stage': 'classifying'})}\n\n"
                        except Exception as e:
                            print(f"Audio error: {e}")
                    
                    prompt = f"Based on the image, classify this text: '{text}' using these categories: {unique_categories}. Output only one category."
                    label = call_qwen_vision_api(image_base64_full, prompt)
                    
                    high_risk.append(label)
                    field_info.append({
                        'text': text, 
                        'label': label, 
                        'index': idx,
                        'bbox_2d': data_extracted[idx]['bbox_2d']
                    })

                try:
                    audio = text_to_audio_base64(f"Classification complete.")
                    yield f"data: {json.dumps({'audio': audio, 'text': f'Classifying {len(texts)} text regions', 'stage': 'classifying'})}\n\n"
                except Exception as e:
                    print(f"Audio error: {e}")
                 
                
                crop_x = bbox_orig[0]
                crop_y = bbox_orig[1]
                
                import uuid
                if not session_id:
                    session_id = str(uuid.uuid4())
                
                detection_cache[session_id] = {
                    'image': image,
                    'hr_im': hr_im,
                    'field_info': field_info,
                    'bbox_orig': bbox_orig,
                    'crop_x': crop_x,
                    'crop_y': crop_y,
                    'total_angle': total_angle,
                    'cropped_image_tmp': cropped_image_tmp,
                    'rotated_image_v1': rotated_image_v1
                }
                
                sensitive_fields = [f for f in field_info if f['label'] not in ['none', 'other']]
                
                try:
                    audio = text_to_audio_base64("Do you want to proceed with regular masking? Say yes or no.")
                    yield f"data: {json.dumps({'audio': audio, 'text': 'Awaiting user response', 'stage': 'awaiting_response', 'request_user_input': True, 'session_id': session_id})}\n\n"
                except Exception as e:
                    print(f"Audio error: {e}")
                return
    
            else:
                has_private = False
                try:
                    audio = text_to_audio_base64("No private document detected in the image.")
                    yield f"data: {json.dumps({'audio': audio, 'text': 'No private document detected', 'stage': 'none'})}\n\n"
                except Exception as e:
                    print(f"Audio error: {e}")
                
                yield f"data: {json.dumps({'done': True, 'detection': detection_result, 'has_private_info': has_private, 'cropped_image': None})}\n\n"
            
        except Exception as e:
            print(f'Exception: {str(e)}')
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')           

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=3000, debug=False)
