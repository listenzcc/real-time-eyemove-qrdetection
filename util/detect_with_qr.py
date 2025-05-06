import time
import requests
import numpy as np

from PIL import Image
from qreader import QReader
from threading import Thread, RLock
from loguru import logger

qreader = QReader()


def detect_qr_code(image: Image):
    image = image.convert('RGB')

    found = qreader.detect(
        image=np.array(image), is_bgr=True)

    n = len(found)
    print(n)
    assert n >= 3, f'Require at least 3 qr-codes.'

    data = []
    for pnt in found:
        # print(pnt)
        x1, y1, x2, y2 = pnt['bbox_xyxyn']
        # print(f'{i} | {n}', (x1, y1, x2, y2))
        data.append((x1, y1, x2, y2))

    data.sort(key=lambda e: e[0])
    if data[0][1] < data[1][1]:
        nw = data[0]
        sw = data[1]
        ne = data[n-1]
    else:
        nw = data[1]
        sw = data[0]
        ne = data[n-1]

    nw = [nw[0], nw[1]]
    sw = [sw[0], sw[3]]
    ne = [ne[2], ne[1]]

    found = [nw, sw, ne]

    return found


def send_coordinates(x, y):
    try:
        # Construct the URL with query parameters
        url = f"http://localhost:8080/?x={x}&y={y}"

        # Send the GET request
        response = requests.get(url)

        # Print the server's response
        print(f"Server response: {response.text}")
    except Exception as e:
        print(f"Error sending coordinates: {e}")


class QrDetector:
    image: Image = None
    x: int = 0
    y: int = 0
    running: bool = False
    lock = RLock()

    def update(self, image: Image, x: int, y: int):
        with self.lock:
            self.image = image
            self.x = x
            self.y = y

    def start_service(self):
        Thread(target=self.main_loop, daemon=True).start()
        logger.info(f'Start service: {self}.')

    def stop_service(self):
        self.running = False
        logger.info(f'Stop service: {self}.')

    def main_loop(self):
        logger.info('Main loop starts.')
        self.running = True
        while self.running:
            if self.image is None:
                time.sleep(0.1)
                continue

            with self.lock:
                img = self.image.copy()
                x = self.x
                y = self.y

            try:
                corners = detect_qr_code(img)
            except Exception:
                # import traceback
                # traceback.print_exc()
                time.sleep(0.1)
                continue

            try:
                print(corners)
                nw, sw, ne = corners
                x_axis = np.array(ne) - np.array(nw)
                y_axis = np.array(sw) - np.array(nw)
                p = np.array([x, y]) - np.array(nw)
                rx = np.dot(p, x_axis) / np.dot(x_axis, x_axis)
                ry = np.dot(p, y_axis) / np.dot(y_axis, y_axis)
                print(x, y, rx, ry)
                send_coordinates(rx, ry)
            except Exception:
                import traceback
                traceback.print_exc()
            finally:
                time.sleep(0.1)

        logger.info('Main loop stops.')
