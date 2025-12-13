from gradio_client import Client, handle_file
import cv2

sam3 = Client("akhaliq/sam3")

def get_mask():


    result = sam3.predict(
        image=handle_file('cropped_image.jpg'),
        text="the document",
        threshold=0.5,
        mask_threshold=0.5,
        api_name="/segment"
    )

    img = cv2.imread(result[0]['annotations'][0]['image'])
    pred_mask = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    pred_mask = pred_mask > 0

    return pred_mask
