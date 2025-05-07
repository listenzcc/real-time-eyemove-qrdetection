import time
import requests
import numpy as np
import socket  # Add this import

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
        # Establish a TCP connection
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            # Connect to the TCP server
            client_socket.connect(('localhost', 8080))
            message = f"x={x}&y={y}"  # Format the message
            client_socket.sendall(message.encode())  # Send the message
            response = client_socket.recv(
                1024).decode()  # Receive the response
            print(f"Server response: {response}")
    except Exception as e:
        print(f"Error sending coordinates: {e}")


class QrDetector:
    # Real time image
    image: Image = None

    # Corners
    corners: list = None

    # Real time gaze position
    x: int = 0
    y: int = 0

    # Whether is running
    running: bool = False

    # RLock
    lock = RLock()

    def update(self, image: Image, x: int, y: int):
        with self.lock:
            self.image = image
            self.x = x
            self.y = y

    def start_service(self):
        self.running = True
        Thread(target=self.slow_loop, daemon=True).start()
        Thread(target=self.main_loop, daemon=True).start()
        logger.info(f'Start service: {self}.')

    def stop_service(self):
        self.running = False
        logger.info(f'Stop service: {self}.')

    def slow_loop(self):
        '''
        Detect the qr-codes in the slow loop.
        The detection is rather slow, like 2 ~ 5 fps.
        '''
        logger.info('Slow loop starts.')
        while self.running:
            if self.image is None:
                time.sleep(0.1)
                continue

            with self.lock:
                img = self.image.copy()

            try:
                corners = detect_qr_code(img)
            except Exception as err:
                logger.exception(err)
                time.sleep(0.1)
                continue

            with self.lock:
                self.corners = corners

        logger.info('Slow loop stops.')

    def main_loop(self):
        '''
        Translate gaze position in the main loop.
        I except it very fast.
        '''
        logger.info('Main loop starts.')
        while self.running:
            if self.corners is None:
                time.sleep(0.1)
                continue

            with self.lock:
                x = self.x
                y = self.y
                corners = self.corners

            try:
                nw, sw, ne = corners
                x_axis = np.array(ne) - np.array(nw)
                y_axis = np.array(sw) - np.array(nw)
                p = np.array([x, y]) - np.array(nw)
                rx = np.dot(p, x_axis) / np.dot(x_axis, x_axis)
                ry = np.dot(p, y_axis) / np.dot(y_axis, y_axis)
                logger.debug(f'Corners: {corners}')
                logger.debug('Positions: {}'.format(
                    ', '.join([f'{e:.4f}' for e in [x, y, rx, ry]])))
                send_coordinates(rx, ry)
            except Exception:
                import traceback
                traceback.print_exc()
            finally:
                time.sleep(0.001)

        logger.info('Main loop stops.')
