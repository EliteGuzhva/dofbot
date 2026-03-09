import cv2
import time
import math
import numpy as np
import threading

from messaging import Publisher, Subscriber, Message, msgs


should_stop = False


def worker():
    publisher = Publisher()

    center = np.array([0.0, 0.1, 0.2])
    radius = 0.05
    angle = 0
    speed = 20

    topic = "/cmd"
    while not should_stop:
        ts = time.time()

        t = center + radius * np.array(
            [math.cos(math.radians(angle)), 0.0, math.sin(math.radians(angle))]
        )
        angle += speed
        if angle >= 360:
            angle = 0

        payload = msgs.Cmd(
            time=200,
            position=t.tolist(),
            gripper_open=True if angle < 180 else False,
        )

        msg = Message(topic=topic, timestamp=ts, payload=payload)
        print(msg)
        publisher.publish(msg)

        time.sleep(0.2)


def process_image(msg: Message):
    if msg.raw_data is None:
        return

    print(msg.topic, msg.timestamp, msg.payload)
    image = msgs.Image(**msg.payload)
    frame = image.to_numpy(msg.raw_data)
    frame = cv2.rotate(frame, cv2.ROTATE_180)
    cv2.imshow("Image", frame)
    cv2.waitKey(1)


subscriber = Subscriber(host="192.168.4.228")
subscriber.subscribe("/image", process_image)

thread = threading.Thread(target=worker)
thread.start()

while True:
    try:
        subscriber.loop()
    except KeyboardInterrupt:
        subscriber.stop()
        should_stop = True
        thread.join()
        break
