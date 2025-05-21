import os
import cv2
import numpy as np
import dlib
from ultralytics import YOLO # Corrected import based on standard usage
import onnxruntime

# Define constants for model paths and alignment parameters
YOLO_MODEL_PATH = "backend/ml_models/yolov11n-face.pt"
DLIB_PREDICTOR_PATH = "backend/ml_models/shape_predictor_68_face_landmarks.dat"
ARCFACE_MODEL_PATH = "backend/ml_models/arcface_model.onnx"

OUTPUT_SIZE = (112, 112) # For aligned faces, typical for ArcFace
DETECTION_CONFIDENCE = 0.6
MIN_FACE_SIZE = 32

# Initialize models globally
yolo_detector = None
dlib_predictor = None
arcface_session = None

def load_models():
    global yolo_detector, dlib_predictor, arcface_session
    if not os.path.exists(YOLO_MODEL_PATH):
        # This is a critical error, should stop the application or indicate severe degradation
        print(f"CRITICAL ERROR: YOLO model not found at {YOLO_MODEL_PATH}")
        raise FileNotFoundError(f"YOLO model not found at {YOLO_MODEL_PATH}")
    if not os.path.exists(DLIB_PREDICTOR_PATH):
        print(f"CRITICAL ERROR: Dlib predictor not found at {DLIB_PREDICTOR_PATH}")
        raise FileNotFoundError(f"Dlib predictor not found at {DLIB_PREDICTOR_PATH}")
    if not os.path.exists(ARCFACE_MODEL_PATH):
        print(f"CRITICAL ERROR: ArcFace model not found at {ARCFACE_MODEL_PATH}")
        raise FileNotFoundError(f"ArcFace model not found at {ARCFACE_MODEL_PATH}")

    try:
        yolo_detector = YOLO(YOLO_MODEL_PATH)
        dlib_predictor = dlib.shape_predictor(DLIB_PREDICTOR_PATH)
        # Consider providers carefully for ONNX Runtime, e.g., ['CPUExecutionProvider']
        arcface_session = onnxruntime.InferenceSession(ARCFACE_MODEL_PATH, providers=['CPUExecutionProvider'])
        print("Face processing models loaded successfully.")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to load one or more ML models: {e}")
        # Depending on application design, might want to re-raise or exit
        raise RuntimeError(f"Failed to load ML models: {e}")


def align_single_face(image_rgb, rect_coords, predictor, output_size=OUTPUT_SIZE):
    """
    Aligns a single face found in an image.
    :param image_rgb: NumPy array of the input image (RGB).
    :param rect_coords: Tuple (x1, y1, x2, y2) for the detected face.
    :param predictor: dlib shape predictor object.
    :param output_size: Tuple (width, height) for the output aligned face.
    :return: NumPy array of the aligned face (RGB), or None if alignment fails.
    """
    if predictor is None:
        # This check should ideally be done before calling this function (e.g. in load_models)
        # but as a safeguard:
        print("ERROR: Dlib predictor not loaded in align_single_face.")
        return None

    x1, y1, x2, y2 = rect_coords
    rect = dlib.rectangle(x1, y1, x2, y2)
    
    shape = predictor(image_rgb, rect)
    
    # Estimate eye centers - points 36-41 are left eye, 42-47 are right eye
    left_eye_pts = np.array([(shape.part(i).x, shape.part(i).y) for i in range(36, 42)])
    right_eye_pts = np.array([(shape.part(i).x, shape.part(i).y) for i in range(42, 48)])
    
    left_eye_center = left_eye_pts.mean(axis=0).astype("int")
    right_eye_center = right_eye_pts.mean(axis=0).astype("int")
    
    # Compute angle between the eye centers
    dy = right_eye_center[1] - left_eye_center[1]
    dx = right_eye_center[0] - left_eye_center[0]
    angle = np.degrees(np.arctan2(dy, dx))
    
    # Eye distance for scaling
    eye_dist = np.sqrt(dx**2 + dy**2)
    if eye_dist == 0: # Avoid division by zero
        return None
        
    # Desired left eye proportion in the output image (typical value)
    desired_left_eye_x_prop = 0.36
    desired_eye_dist_prop = 0.28 # Proportion of output width that eyes should span
    
    desired_face_width = output_size[0]
    desired_face_height = output_size[1]
    
    # Calculate scale factor
    scale = (desired_face_width * desired_eye_dist_prop) / eye_dist
    
    # Get the center of the eyes
    eyes_center = ((left_eye_center[0] + right_eye_center[0]) // 2,
                   (left_eye_center[1] + right_eye_center[1]) // 2)
    
    # Get rotation matrix
    M = cv2.getRotationMatrix2D(eyes_center, angle, scale)
    
    # Update translation part of the matrix
    tX = desired_face_width * 0.5
    tY = desired_face_height * desired_left_eye_x_prop # Shift based on desired left eye y position
    
    M[0, 2] += (tX - eyes_center[0])
    M[1, 2] += (tY - eyes_center[1])
    
    # Apply affine transformation
    aligned_face = cv2.warpAffine(image_rgb, M, (desired_face_width, desired_face_height), flags=cv2.INTER_CUBIC)
    
    return aligned_face # RGB image


def detect_faces(image_rgb, yolo=None, confidence_threshold=DETECTION_CONFIDENCE, min_face_size=MIN_FACE_SIZE):
    """
    Detects faces in an image using YOLO.
    :param image_rgb: NumPy array of the input image (RGB).
    :param yolo: YOLO detector object.
    :param confidence_threshold: Minimum confidence for a detection to be considered.
    :param min_face_size: Minimum size (width or height) for a detected face.
    :return: List of face rectangles [(x1, y1, x2, y2), ...].
    """
    # Use global yolo_detector if yolo parameter is None
    current_yolo_detector = yolo if yolo is not None else yolo_detector
    if current_yolo_detector is None:
        print("ERROR: YOLO model not loaded in detect_faces.")
        # Depending on strictness, could raise ValueError or return empty list
        return [] 

    results = current_yolo_detector(image_rgb, verbose=False)[0] # Assuming results[0] contains detections
    detected_faces = []
    for box in results.boxes:
        conf = box.conf.item()
        if conf < confidence_threshold:
            continue
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        if (x2 - x1) < min_face_size or (y2 - y1) < min_face_size:
            continue
        detected_faces.append((x1, y1, x2, y2))
    return detected_faces


def get_embedding_from_aligned_face(aligned_face_rgb, session=None):
    """
    Extracts ArcFace embedding from an aligned face image.
    :param aligned_face_rgb: NumPy array of the aligned face (112x112 RGB).
    :param session: ONNX Runtime session for ArcFace model.
    :return: NumPy array (embedding vector).
    """
    current_arcface_session = session if session is not None else arcface_session
    if current_arcface_session is None:
        print("ERROR: ArcFace model not loaded in get_embedding_from_aligned_face.")
        # Depending on strictness, could raise ValueError or return None/empty array
        return np.array([])

    # Preprocessing specific to ArcFace model
    img = cv2.cvtColor(aligned_face_rgb, cv2.COLOR_RGB2BGR) # ArcFace often expects BGR
    img = (img.astype(np.float32) - 127.5) / 128.0
    img = img.transpose((2, 0, 1)) # HWC to CHW (112, 112, 3) -> (3, 112, 112)
    input_blob = np.expand_dims(img, axis=0) # Add batch dimension (1, 3, 112, 112)

    input_name = current_arcface_session.get_inputs()[0].name
    output_name = current_arcface_session.get_outputs()[0].name
    
    embedding = current_arcface_session.run([output_name], {input_name: input_blob})[0]
    embedding = embedding.flatten() # Ensure it's a 1D vector
    
    # Normalize the embedding (L2 normalization)
    norm = np.linalg.norm(embedding)
    if norm == 0: 
        # This case might indicate an issue or a zero vector, handle as appropriate
        print("Warning: Zero norm for embedding.")
        return embedding 
    embedding = embedding / norm
    return embedding


def get_face_embeddings_from_image_bytes(image_bytes: bytes) -> list[np.ndarray]:
    """
    Main function to process an image from bytes, detect faces, align them, and extract embeddings.
    :param image_bytes: Bytes of the input image.
    :return: List of NumPy arrays (embeddings), or empty list if errors or no faces.
    """
    # Ensure models are loaded (this is critical)
    if yolo_detector is None or dlib_predictor is None or arcface_session is None:
        print("ERROR: Models not loaded. Call load_models() before processing.")
        # Depending on design, could try to call load_models() here, but it's better if App calls it explicitly at startup.
        # For this subtask, we'll assume they are loaded by the module-level call or an explicit app init.
        # If not, this function will fail when sub-functions try to access None models.
        # Returning empty list for now if models aren't loaded.
        return []

    # 1. Decode image_bytes to OpenCV image (RGB)
    nparr = np.frombuffer(image_bytes, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        print("Warning: Could not decode image from bytes.")
        return []
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    # 2. Detect faces
    # Pass the globally loaded models explicitly to ensure clarity and testability,
    # or rely on them being available in the global scope of the sub-functions.
    face_rects = detect_faces(img_rgb, yolo=yolo_detector)
    if not face_rects:
        # print("No faces detected in the image.") # This can be noisy if called often
        return []

    embeddings = []
    for rect in face_rects:
        # 3. Align each face
        aligned_face = align_single_face(img_rgb, rect, predictor=dlib_predictor)
        if aligned_face is None:
            # print(f"Warning: Failed to align face at rect {rect}.")
            continue # Skip if alignment fails

        # 4. Get embedding for each aligned face
        embedding = get_embedding_from_aligned_face(aligned_face, session=arcface_session)
        if embedding.size == 0: # Check if embedding extraction failed
            # print(f"Warning: Failed to get embedding for aligned face from rect {rect}.")
            continue
        embeddings.append(embedding)
    
    return embeddings

# Call load_models() at module level to ensure models are loaded on import.
# This might impact server startup time and behavior in some deployment scenarios (e.g. multiple workers).
# An explicit initialization function called by the main app is often preferred for more control.
try:
    load_models()
except Exception as e:
    # Log the error prominently. The application might not be able to start or function correctly.
    print(f"FATAL: Failed to initialize face_processor module due to model loading errors: {e}")
    # Depending on the application's error handling strategy, this might re-raise,
    # or the functions above will fail if models are None.
    # For now, the functions above have checks for None models.
    pass