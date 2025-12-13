import requests
import os
import re
import json
from huggingface_hub import InferenceClient

HF_API_KEY = os.environ.get("HUGGINGFACE_API_KEY")
client = InferenceClient(api_key=HF_API_KEY)

def call_qwen_vision_api(img_b64, prompt):
    """
    Make API request to Qwen vision model
    """
    try:
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

