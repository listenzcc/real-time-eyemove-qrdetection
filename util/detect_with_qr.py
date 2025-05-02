import time
import numpy as np

from PIL import Image
from qreader import QReader
from threading import Thread, RLock
from loguru import logger

qreader = QReader()


def detect_qr_code(image: Image):
    image = image.convert('RGB')

    found = qreader.detect_and_decode(
        image=np.array(image), return_detections=True)

    n = len(found[1])
    qr_codes = []
    for pnt in found[1]:
        # print(pnt)
        x1, y1, x2, y2 = pnt['bbox_xyxy']
        # print(f'{i} | {n}', (x1, y1, x2, y2))
        qr_codes.append((x1, y1, x2, y2))

    return qr_codes


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
                time.sleep(100)

            with self.lock:
                img = self.image.copy()
                x = self.x
                y = self.y

            qr_codes = detect_qr_code(img)
            print(qr_codes)
        logger.info('Main loop stops.')
