from ultralytics import YOLO
import cv2
from pathlib import Path

def detect_street_objects(image_path, output_path="results/annotated.jpg"):
    model = YOLO("yolov8n.pt")
    results = model.predict(source=image_path, imgsz=640, conf=0.25, classes=[0, 2])  # person=0, car=2
    annotated_img = results[0].plot()
    Path("results").mkdir(exist_ok=True)
    cv2.imwrite(output_path, annotated_img[..., ::-1])  # RGB->BGR
    print(f"✅ Saved annotated image to {output_path}")

if __name__ == "__main__":
    detect_street_objects("data/street.jpg")
