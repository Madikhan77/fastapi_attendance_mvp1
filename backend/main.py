import os
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse # Added
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import datetime, timedelta
import shutil # Added
import os # Already present, but good to note for UPLOADS_DIR

import crud, models, schemas
from database import SessionLocal, engine, Base
import backend.face_processor as face_processor
import backend.vector_db as vector_db

# Инициализация
models.Base.metadata.create_all(bind=engine)

# File Uploads Directory
UPLOADS_DIR = "uploads/lesson_files"
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Face Recognition Threshold (lower is better for L2 distance)
FACE_RECOGNITION_THRESHOLD = 0.6 

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Конфиг JWT
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# DB dependency

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# Аутентификация

def authenticate(db: Session, username: str, password: str):
    user = crud.get_user_by_username(db, username)
    if user and crud.pwd_context.verify(password, user.hashed_password):
        return user
    return None

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None: raise
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user = crud.get_user_by_username(db, username)
    if user is None: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user

# Маршруты

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate(db, form_data.username, form_data.password)
    if not user: raise HTTPException(status_code=400, detail="Incorrect credentials")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/users", response_model=schemas.UserRead)
async def api_create_user(user: schemas.UserCreate, current: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.role != 'teacher': raise HTTPException(403)
    return crud.create_user(db, user)

@app.get("/api/users", response_model=list[schemas.UserRead])
async def api_list_users(current: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.role != 'teacher': raise HTTPException(403)
    return db.query(models.User).all()

@app.post("/api/impersonate/{user_id}")
async def impersonate(user_id: int, current: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.role != 'teacher': raise HTTPException(403)
    target = db.get(models.User, user_id)
    token = create_access_token(data={"sub": target.username})
    return {"access_token": token}

@app.post("/api/attendance/{lesson_id}", response_model=schemas.AttendanceRead)
async def api_mark_attendance(
    lesson_id: int,
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user), # Renamed user to current_user for clarity
    db: Session = Depends(get_db)
):
    # Authorization and Enrollment Check
    if current_user.role == 'student':
        enrollment = crud.get_enrollment(db, student_id=current_user.id, lesson_id=lesson_id)
        if not enrollment:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student not enrolled in this lesson.")
    elif current_user.role == 'teacher':
        # Teachers are assumed to be able to "attend" or bypass face check for now,
        # or this logic needs to be specific. If teachers should not use this endpoint:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teachers cannot mark attendance for themselves using this endpoint.")
        # If teachers CAN mark their own "attendance" without face check (e.g. for testing or special cases):
        # pass
    
    # Read Image and Extract Embedding
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No image file provided.")

    try:
        embeddings = face_processor.get_face_embeddings_from_image_bytes(image_bytes)

        if not embeddings:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No face detected in attendance image.")
        
        if len(embeddings) > 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Multiple faces detected in attendance image. Please ensure only your face is visible.")
        
        query_embedding = embeddings[0]

        # Search for Matching Face in FAISS and Verify
        search_results = vector_db.search_embedding(query_embedding=query_embedding, k=1)

        if not search_results:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Face not recognized in our database.")

        matched_user_id, distance = search_results[0]
        
        if matched_user_id == current_user.id and distance < FACE_RECOGNITION_THRESHOLD:
            verified_similarity_score = max(0.0, 1.0 - distance) # Convert L2 distance to a similarity score (0 to 1)
            
            # Record Attendance
            db_att = crud.create_attendance(db=db, user_id=current_user.id, att=schemas.AttendanceCreate(lesson_id=lesson_id, similarity=verified_similarity_score))
            print(f"Attendance confirmed for user {current_user.username} (ID: {current_user.id}) for lesson {lesson_id} with similarity {verified_similarity_score:.4f}.")
            return schemas.AttendanceRead.model_validate(db_att) # Use model_validate for Pydantic v2
        else:
            detail_msg = f"Face verification failed. Match distance: {distance:.4f}."
            if matched_user_id != current_user.id:
                print(f"Security Alert: User {current_user.username} (ID: {current_user.id}) attendance attempt matched user ID {matched_user_id}.")
                detail_msg = "Face does not match registered profile for the current user."
            
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail_msg)

    except FileNotFoundError as e: 
        print(f"CRITICAL: Model file not found during attendance marking: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Face processing models not available. Please contact support.")
    except ValueError as e: 
        print(f"Value error during attendance marking for user {current_user.username} (ID: {current_user.id}): {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"Unexpected error during attendance marking for user {current_user.username} (ID: {current_user.id}): {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during face verification.")


@app.get("/api/attendance", response_model=list[schemas.AttendanceRead])
async def api_list_attendance(current: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.role not in ['teacher', 'student']: raise HTTPException(403)
    records = crud.get_attendance(db)
    return records

# Lesson Endpoints

@app.post("/api/lessons", response_model=schemas.LessonRead, status_code=status.HTTP_201_CREATED)
async def create_lesson_endpoint(
    lesson: schemas.LessonCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != 'teacher':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only teachers can create lessons")
    return crud.create_lesson(db, lesson=lesson, teacher_id=current_user.id)

@app.get("/api/lessons", response_model=list[schemas.LessonRead])
async def get_lessons_for_teacher_endpoint(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != 'teacher':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only teachers can view their lessons list")
    return crud.get_lessons_by_teacher(db, teacher_id=current_user.id)

@app.get("/api/lessons/{lesson_id}", response_model=schemas.LessonRead)
async def get_lesson_endpoint(
    lesson_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_lesson = crud.get_lesson(db, lesson_id=lesson_id)
    if db_lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    if current_user.role == 'teacher' and db_lesson.teacher_id == current_user.id:
        return db_lesson
    
    if current_user.role == 'student':
        enrollment = crud.get_enrollment(db, student_id=current_user.id, lesson_id=lesson_id)
        if enrollment:
            return db_lesson
            
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this lesson")

@app.put("/api/lessons/{lesson_id}", response_model=schemas.LessonRead)
async def update_lesson_endpoint(
    lesson_id: int,
    lesson_update: schemas.LessonCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_lesson = crud.get_lesson(db, lesson_id=lesson_id)
    if db_lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    if db_lesson.teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the lesson teacher can update it")
    
    updated_lesson = crud.update_lesson(db, lesson_id=lesson_id, lesson_update=lesson_update)
    if updated_lesson is None: # Should not happen if previous checks passed
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found after update attempt")
    return updated_lesson

@app.delete("/api/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson_endpoint(
    lesson_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_lesson = crud.get_lesson(db, lesson_id=lesson_id)
    if db_lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    if db_lesson.teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the lesson teacher can delete it")

    # Delete associated files
    for lesson_file in db_lesson.files:
        file_path = lesson_file.file_path
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as e:
                # Log this error, but continue with deleting the lesson from DB
                print(f"Error deleting file {file_path}: {e}") 
        # No need to call crud.delete_lesson_file here as cascade delete should handle it from LessonFile model,
        # or if not, the lesson deletion itself will make them inaccessible.
        # However, explicit deletion can be done if cascade is not set or for safety.

    deleted_lesson = crud.delete_lesson(db, lesson_id=lesson_id)
    if deleted_lesson is None: # Should not happen if previous checks passed
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found during delete attempt")
    return None # For 204 No Content

# Lesson File Endpoints

@app.post("/api/lessons/{lesson_id}/files", response_model=schemas.LessonFileRead, status_code=status.HTTP_201_CREATED)
async def upload_lesson_file_endpoint(
    lesson_id: int,
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_lesson = crud.get_lesson(db, lesson_id=lesson_id)
    if db_lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    if current_user.role != 'teacher' or db_lesson.teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the lesson teacher can upload files")

    file_location = os.path.join(UPLOADS_DIR, f"{lesson_id}_{db_lesson.id}_{file.filename}") # Added lesson.id to file path for uniqueness
    
    # Ensure the UPLOADS_DIR for the specific lesson exists
    lesson_upload_dir = os.path.join(UPLOADS_DIR, str(lesson_id))
    os.makedirs(lesson_upload_dir, exist_ok=True)
    file_location = os.path.join(lesson_upload_dir, file.filename)


    try:
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
    except Exception as e:
        # Log error e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not save file: {e}")

    db_lesson_file = crud.create_lesson_file(db, file_name=file.filename, file_path=file_location, lesson_id=lesson_id)
    return db_lesson_file

@app.get("/api/lessons/{lesson_id}/files", response_model=list[schemas.LessonFileRead])
async def get_lesson_files_endpoint(
    lesson_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_lesson = crud.get_lesson(db, lesson_id=lesson_id)
    if db_lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    if current_user.role == 'teacher' and db_lesson.teacher_id == current_user.id:
        return crud.get_lesson_files(db, lesson_id=lesson_id)
    
    if current_user.role == 'student':
        enrollment = crud.get_enrollment(db, student_id=current_user.id, lesson_id=lesson_id)
        if enrollment:
            return crud.get_lesson_files(db, lesson_id=lesson_id)
            
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view these files")

@app.get("/api/files/{file_id}/download", response_class=FileResponse)
async def download_lesson_file_endpoint(
    file_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_file = crud.get_lesson_file(db, file_id=file_id)
    if db_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    db_lesson = crud.get_lesson(db, lesson_id=db_file.lesson_id)
    if db_lesson is None: # Should not happen if file exists, but good practice
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated lesson not found")

    if current_user.role == 'teacher' and db_lesson.teacher_id == current_user.id:
        pass # Authorized
    elif current_user.role == 'student':
        enrollment = crud.get_enrollment(db, student_id=current_user.id, lesson_id=db_file.lesson_id)
        if not enrollment:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to download this file")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to download this file")
    
    if not os.path.exists(db_file.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on server")

    return FileResponse(path=db_file.file_path, filename=db_file.filename, media_type='application/octet-stream')

@app.delete("/api/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson_file_endpoint(
    file_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_file = crud.get_lesson_file(db, file_id=file_id)
    if db_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    db_lesson = crud.get_lesson(db, lesson_id=db_file.lesson_id)
    if db_lesson is None: # Should not happen
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated lesson not found")
    
    if current_user.role != 'teacher' or db_lesson.teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the lesson teacher can delete this file")

    file_path = db_file.file_path
    
    deleted_db_file_entry = crud.delete_lesson_file(db, file_id=file_id)
    if deleted_db_file_entry is None: # Should not happen if previous checks passed
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found during delete attempt from DB")

    # Physical file deletion after DB entry is confirmed deleted
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            # Log this error. Consider if this should be a critical failure.
            # For now, we've deleted the DB entry, so the file is orphaned.
            print(f"Error deleting file {file_path}: {e}")
            # Optionally, re-add the DB entry or raise a 500 error if physical deletion is critical
            # crud.create_lesson_file(db, file_name=db_file.filename, file_path=db_file.file_path, lesson_id=db_file.lesson_id) # Rollback DB
            # raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not delete file from disk: {e}")
    
    return None # For 204 No Content

# Student Enrollment Endpoints

@app.post("/api/lessons/{lesson_id}/enroll", response_model=schemas.StudentLessonEnrollmentRead, status_code=status.HTTP_201_CREATED)
async def enroll_student_endpoint(
    lesson_id: int,
    enrollment_req: schemas.StudentLessonEnrollmentCreate, # Assuming user_id is in the body, matching lesson_id from path
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_lesson = crud.get_lesson(db, lesson_id=lesson_id)
    if db_lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    if current_user.role != 'teacher' or db_lesson.teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the lesson teacher can enroll students")

    # Ensure enrollment_req explicitly sets the lesson_id from the path, or that it matches if also in body.
    # For simplicity, we'll assume enrollment_req might only contain user_id if lesson_id is fixed from path.
    # The schema StudentLessonEnrollmentCreate expects both user_id and lesson_id.
    # We will enforce that enrollment_req.lesson_id matches path lesson_id if provided, or use path lesson_id.
    
    if enrollment_req.lesson_id != lesson_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lesson ID in path and request body must match")

    target_user = db.get(models.User, enrollment_req.user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User to enroll not found")
    if target_user.role != 'student':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only enroll users with 'student' role")

    # Check if already enrolled (crud.enroll_student already does this, but can be explicit here)
    existing_enrollment = crud.get_enrollment(db, student_id=enrollment_req.user_id, lesson_id=lesson_id)
    if existing_enrollment:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Student already enrolled in this lesson")

    return crud.enroll_student(db, enrollment=enrollment_req)


@app.delete("/api/lessons/{lesson_id}/unenroll", status_code=status.HTTP_204_NO_CONTENT)
async def unenroll_student_endpoint(
    lesson_id: int,
    # The spec says payload: schemas.StudentLessonEnrollmentBase, which requires user_id and lesson_id
    # This means the client needs to send a body: {"user_id": X, "lesson_id": Y}
    unenroll_req: schemas.StudentLessonEnrollmentBase, 
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_lesson = crud.get_lesson(db, lesson_id=lesson_id)
    if db_lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    if current_user.role != 'teacher' or db_lesson.teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the lesson teacher can unenroll students")

    if unenroll_req.lesson_id != lesson_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lesson ID in path and request body must match")
    
    target_user = db.get(models.User, unenroll_req.user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User to unenroll not found")
    # No need to check role here, if they are enrolled, they should be unenrollable by teacher.

    db_enrollment = crud.unenroll_student(db, student_id=unenroll_req.user_id, lesson_id=lesson_id)
    if db_enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found for this student and lesson")
    
    return None # For 204 No Content

# Student-Specific Endpoints

@app.get("/api/student/lessons", response_model=list[schemas.LessonRead])
async def get_student_lessons_endpoint(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != 'student':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can view their enrolled lessons")
    return crud.get_lessons_for_student(db, student_id=current_user.id)

# User Face Registration Endpoint
@app.post("/api/users/me/register-face", response_model=schemas.MessageResponse)
async def register_face_for_student(
    current_user: models.User = Depends(get_current_user),
    # db: Session = Depends(get_db), # db not directly used here unless for logging user activity
    file: UploadFile = File(...)
):
    if current_user.role != 'student':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can register faces.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No image file provided.")

    try:
        # face_processor and vector_db models/indices are loaded on module import.
        # If they failed to load, their respective functions will handle or raise errors.
        
        embeddings = face_processor.get_face_embeddings_from_image_bytes(image_bytes)

        if not embeddings:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No face detected in the uploaded image. Please upload a clear picture of your face."
            )
        
        if len(embeddings) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Multiple faces detected. Please upload an image with only your face clearly visible."
            )
        
        embedding = embeddings[0]
        
        # Delete any existing embeddings for this user to ensure only one face profile per user.
        try:
            removed_count = vector_db.delete_embeddings_by_user_id(current_user.id)
            if removed_count > 0:
                print(f"Removed {removed_count} existing embeddings for user {current_user.id} before adding new one.")
        except Exception as e:
            # Log this error but proceed with adding the new embedding.
            # If save_faiss_data fails in delete_embeddings_by_user_id, it might be problematic.
            # However, the main goal is to register the new face.
            print(f"Error during pre-deletion of embeddings for user {current_user.id}: {e}")

        faiss_id = vector_db.add_embedding(user_id=current_user.id, embedding=embedding)
        
        print(f"Registered face for user {current_user.username} (ID: {current_user.id}), FAISS ID (internal): {faiss_id}") # For logging

        return schemas.MessageResponse(message="Face registered successfully.")

    except FileNotFoundError as e: 
        # This might occur if model files were deleted after initial load, or if load_models() was skipped/failed silently.
        print(f"CRITICAL: Model file not found during face registration: {e}") # Changed to print for server log
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Face processing models not available. Please contact support.")
    except ValueError as e: 
        print(f"Value error during face registration for user {current_user.username} (ID: {current_user.id}): {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"Unexpected error during face registration for user {current_user.username} (ID: {current_user.id}): {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during face registration.")