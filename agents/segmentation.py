from gradio_client import Client, handle_file
import numpy as np
import cv2

sam3 = Client("akhaliq/sam3")

def get_mask():


    result = sam3.predict(
        image=handle_file('cropped_image.jpg'),
        text="document",
        threshold=0.3,
        mask_threshold=0.5,
        api_name="/segment"
    )

    if len(result[0]['annotations']) == 0:
        img = cv2.imread(result[0]['image'])
        rows, cols, _ = img.shape
        pred_mask = np.ones((rows, cols), dtype=bool)
    else:
        img = cv2.imread(result[0]['annotations'][0]['image'])
        pred_mask = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        pred_mask = pred_mask > 0

    return pred_mask
