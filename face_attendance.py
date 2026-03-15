import cv2
import os
import numpy as np
import requests
import time

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

faces_path = "faces"

faces = []
labels = []
names = {}

label_id = 0

for file in os.listdir(faces_path):

    path = os.path.join(faces_path, file)
    img = cv2.imread(path, 0)

    detected = face_cascade.detectMultiScale(img,1.3,5)

    for (x,y,w,h) in detected:

        faces.append(img[y:y+h,x:x+w])
        labels.append(label_id)

        names[label_id] = file.split(".")[0]

    label_id += 1

recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.train(faces, np.array(labels))

cap = cv2.VideoCapture(0)

cooldown = 600
last_mark = 0

print("Face recognition started")

while True:

    ret, frame = cap.read()

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    detected = face_cascade.detectMultiScale(gray,1.3,5)

    for (x,y,w,h) in detected:

        face = gray[y:y+h,x:x+w]

        id, confidence = recognizer.predict(face)

        if confidence < 70:

            name = names[id]

            cv2.putText(frame,name,(x,y-10),
                        cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)

            if time.time() - last_mark > cooldown:

                print(name,"attendance marked")

                requests.post(
                    "http://127.0.0.1:8000/api/attendance",
                    json={
                        "card_uid":"12345",
                        "action":"IN"
                    }
                )

                last_mark = time.time()

        else:

            cv2.putText(frame,"Unknown",(x,y-10),
                        cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)

        cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)

    cv2.imshow("SmartEdu Face Attendance",frame)

    if cv2.waitKey(1)==27:
        break

cap.release()
cv2.destroyAllWindows()
