import os
import threading
import time
import struct
from threading import *
from PyQt5 import QtCore
from PyQt5.QtGui import QImage, QPixmap
from sdk_types import *
import ctypes


class wrapper:
    ui_handle = None

    h256_dll_handle = None
    sdk_dll_handle = None
    sdk_config_path = None

    py_camera_state_cb = None
    py_image_cb = None
    py_gaze_cb = None
    py_left_point_process_cb = None
    py_right_point_process_cb = None
    py_left_point_finish_cb = None
    py_right_point_finish_cb = None

    left_img_count = 0
    right_img_count = 0

    thread_handle = None
    select_Point_event = threading.Event()
    flag_exit_thread = False
    thread_is_running = False
    calib_points = None
    cur_point_x = 0.0
    cur_point_y = 0.0

    scene_img_size_max = 1920 * 1080 * 3
    # scene_img_buf = bytes(scene_img_size_max)

    scene_img_buf = py_7i_bytes()

    def set_current_point(self, x, y):
        self.cur_point_x = float(x)
        self.cur_point_y = float(y)
        self.select_Point_event.set()
        print('set_current_point %f %f' % (self.cur_point_x, self.cur_point_y))

    @staticmethod
    def set_ui_handle(ui_object):
        wrapper.ui_handle = ui_object

    @staticmethod
    def camera_state_callback(state, context):
        self = context
        print('enter camera_state_callback')
        print('state:%d' % state)

    @staticmethod
    def image_callback(eye, image, size, width, height, timestamp, context):
        self = context
        if 13 == eye:  # scene images
            ptr = ctypes.cast(image, ctypes.c_void_p)
            self.h256_dll_handle._7i_h265_decode(
                size, ptr, self.scene_img_buf.data, self.scene_img_size_max)
            img = QPixmap.fromImage(QImage(
                self.scene_img_buf.data, width, height, QImage.Format_BGR888))  # BGR Image

            # img = QPixmap.fromImage(QImage(image, width, height, QImage.Format_BGR888))  # BGR Image
            wrapper.ui_handle.set_scene_image_signal.emit(img)
        else:
            if PY_7I_EYE_TYPE.L_EYE.value == eye:
                img = QPixmap.fromImage(QImage(image, width, height, QImage.Format_Indexed8).scaled(
                    160, 120, QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation))  # Gray Image
                wrapper.ui_handle.set_left_eye_image_signal.emit(img)
            elif PY_7I_EYE_TYPE.R_EYE.value == eye:
                img = QPixmap.fromImage(QImage(image, width, height, QImage.Format_Indexed8).scaled(
                    160, 120, QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation))  # Gray Image
                wrapper.ui_handle.set_right_eye_image_signal.emit(img)

    @staticmethod
    def gaze_callback(eyes, context):
        self = context
        obj = eyes.__getitem__(0)

        score_id = PY_7I_EYE_GAZE_EX_DATA_VALIDITY.ID_EYE_GAZE_EXDATA_SCORE.value
        left_score_valid = self.sdk_dll_handle._7i_get_valid_value(
            score_id, obj.left_gaze.ex_data_bit_mask)
        right_score_valid = self.sdk_dll_handle._7i_get_valid_value(
            score_id, obj.right_gaze.ex_data_bit_mask)
        # if 1 == left_score_valid:
        #    print(obj.left_gaze.ex_data[score_id])   # Left eye calibration score (10 point scale)
        # if 1 == right_score_valid:
        #    print(obj.right_gaze.ex_data[score_id])  # right eye calibration score (10 point scale)

        wrapper.ui_handle.set_pupil_center_signal.emit(
            obj.left_pupil.pupil_center.x, obj.left_pupil.pupil_center.y,
            obj.right_pupil.pupil_center.x, obj.right_pupil.pupil_center.y)

        wrapper.ui_handle.set_gaze_signal.emit(
            obj.recom_gaze.gaze_point.x, obj.recom_gaze.gaze_point.y)

    @staticmethod
    def left_point_process_callback(index, percent, context):
        self = context
        print("left process:%d %d" % (index, percent))

    @staticmethod
    def right_point_process_callback(index, percent, context):
        self = context
        print("right process:%d %d" % (index, percent))

    @staticmethod
    def left_point_finish_callback(index, error, context):
        self = context
        print("left finish:%d %d" % (index, error))
        wrapper.ui_handle.set_calibration_finish_signal.emit(0, index, error)

    @staticmethod
    def right_point_finish_callback(index, error, context):
        self = context
        print("right finish:%d %d" % (index, error))
        wrapper.ui_handle.set_calibration_finish_signal.emit(1, index, error)

    def __init__(self):
        self.py_status_cb = func_camera_state_callback_t(
            wrapper.camera_state_callback)
        self.py_image_cb = func_image_callback_t(wrapper.image_callback)
        self.py_gaze_cb = func_gaze_callback_t(wrapper.gaze_callback)
        self.py_left_point_process_cb = func_point_process_callback_t(
            wrapper.left_point_process_callback)
        self.py_left_point_finish_cb = func_point_finish_callback_t(
            wrapper.left_point_finish_callback)
        self.py_right_point_process_cb = func_point_finish_callback_t(
            wrapper.right_point_process_callback)
        self.py_right_point_finish_cb = func_point_finish_callback_t(
            wrapper.right_point_finish_callback)

    def load_library(self, path):
        self.sdk_config_path = path  # path to the SDK configuration file
        self.sdk_dll_handle = WinDLL('../../bin/aSeeX.dll')
        self.h256_dll_handle = WinDLL('../../bin/H265Decode.dll')
        print(self.sdk_dll_handle)

    def connect_softdog(self, password) -> int:
        ukey_info = py_7i_ukey_info_t()
        ptr_ukey_info = pointer(ukey_info)
        ret = self.sdk_dll_handle._7i_device_connect(password, ptr_ukey_info)
        print('_7i_device_connect:%d' % ret)
        return ret

    def start(self, environment, resolution, img_width, img_height) -> int:
        self.left_img_count = 0
        self.right_img_count = 0
        self.sdk_dll_handle._7i_set_camera_state_callback(
            self.py_status_cb, py_object(self))
        self.sdk_dll_handle._7i_set_image_callback(
            self.py_image_cb, py_object(self))
        self.sdk_dll_handle._7i_set_gaze_callback(
            self.py_gaze_cb, py_object(self))

        ret = self.h256_dll_handle._7i_h265_init(img_width, img_height)
        print('_7i_h265_init:%d' % ret)

        enable_gyroscope = 0
        print('sdk config path:%s' % self.sdk_config_path)
        ret = self.sdk_dll_handle._7i_start(
            self.sdk_config_path, environment, resolution, enable_gyroscope)
        print('_7i_start:%d' % ret)
        return ret

    def stop(self):
        ret = self.sdk_dll_handle._7i_stop()
        print('_7i_stop:%d' % ret)
        self.h256_dll_handle._7i_h265_release()

    def start_calibration(self, points):
        print('enter start_calibration')
        if not self.thread_is_running:
            self.calib_points = points
            self.flag_exit_thread = False
            self.thread_handle = threading.Thread(
                target=self.calibration_thread_func)
            self.thread_handle.start()
        print('leave start_calibration')

    def cancel_current_calibration_point(self):
        self.sdk_dll_handle._7i_cancel_calibration(PY_7I_EYE_TYPE.L_EYE.value)
        self.sdk_dll_handle._7i_cancel_calibration(PY_7I_EYE_TYPE.R_EYE.value)

    def stop_calibration(self):
        print('enter complete_calibration')
        if self.thread_is_running:
            self.flag_exit_thread = True
            wrapper.select_Point_event.set()
            self.thread_handle.join()
        print('leave complete_calibration')

    def calibration_thread_func(self):
        self.thread_is_running = True
        ret = self.sdk_dll_handle._7i_start_calibration(self.calib_points)
        print("_7i_start_calibration: %d" % ret)

        index = 0
        for i in range(index, self.calib_points):
            wrapper.select_Point_event.clear()
            # Wait to select the calibration point event on the screen
            wrapper.select_Point_event.wait()
            if self.flag_exit_thread:
                break  # Exit for

            index = (i + 1)
            pt = py_7i_point2d_t()
            pt.x = self.cur_point_x
            pt.y = self.cur_point_y

            ret1 = self.sdk_dll_handle._7i_start_calibration_point(PY_7I_EYE_TYPE.L_EYE.value, index, pointer(pt),
                                                                   self.py_left_point_process_cb, py_object(
                                                                       self),
                                                                   self.py_left_point_finish_cb, py_object(self))

            ret2 = self.sdk_dll_handle._7i_start_calibration_point(PY_7I_EYE_TYPE.R_EYE.value, index, pointer(pt),
                                                                   self.py_right_point_process_cb, py_object(
                                                                       self),
                                                                   self.py_right_point_finish_cb, py_object(self))

            print("_7i_start_calibration_point: %d %d" % (ret1, ret2))

        time.sleep(3)  # Wait for the last calibration point to complete，
        # In addition, a better approach is to control based on the state of the finish callback,
        # That would be more perfect !!!

        left_coe = py_7i_coefficient_t()
        right_coe = py_7i_coefficient_t()
        ret1 = self.sdk_dll_handle._7i_compute_calibration(
            PY_7I_EYE_TYPE.L_EYE.value, pointer(left_coe))
        ret2 = self.sdk_dll_handle._7i_compute_calibration(
            PY_7I_EYE_TYPE.R_EYE.value, pointer(right_coe))
        print("_7i_compute_calibration: %d %d" % (ret1, ret2))
        if 0 == ret1 and 0 == ret2:
            left_buf_len = c_int(1024)
            flag_left_coe = b'biLeft'
            print(len(flag_left_coe))
            ret1 = self.sdk_dll_handle._7i_get_data(flag_left_coe, len(
                flag_left_coe), left_coe.buf, byref(left_buf_len))
            print("_7i_get_data: L %d %d" % (ret1, left_buf_len.value))

            right_buf_len = c_int(1024)
            flag_right_coe = b'biRight'
            ret2 = self.sdk_dll_handle._7i_get_data(flag_right_coe, len(
                flag_right_coe), right_coe.buf, byref(right_buf_len))
            print("_7i_get_data: R %d %d" % (ret2, right_buf_len.value))

            score_buf_len = c_int(64)
            flag_score = b'get_score'
            score_buf = (c_char * 64)()
            ret3 = self.sdk_dll_handle._7i_get_data(
                flag_score, len(flag_score), score_buf, byref(score_buf_len))
            print("_7i_get_data: S %d %d" % (ret3, score_buf_len.value))
            print(score_buf.value.decode('utf-8'))

        ret = self.sdk_dll_handle._7i_complete_calibration()
        print("_7i_complete_calibration: %d" % ret)

        if 0 == ret1 and 0 == ret2:
            # self.sdk_dll_handle._7i_start_tracking(PY_7I_EYE_TYPE.L_EYE.value, pointer(left_coe))
            ret1 = 0
            # self.sdk_dll_handle._7i_start_tracking(PY_7I_EYE_TYPE.R_EYE.value, pointer(right_coe))
            ret2 = 0
            # print("_7i_start_tracking: %d %d" % (ret1, ret2))
            left_buf_len = c_int(1024)
            flag_left_coe = b'biLeft'
            right_buf_len = c_int(1024)
            flag_right_coe = b'biRight'
            ret1 = self.sdk_dll_handle._7i_set_data(
                flag_left_coe, len(flag_left_coe), left_coe.buf, left_buf_len)
            ret2 = self.sdk_dll_handle._7i_set_data(
                flag_right_coe, len(flag_right_coe), right_coe.buf, right_buf_len)
            print("_7i_set_data: L %d" % (ret1))

        self.thread_is_running = False

    def start_tracking(self):
        local_left_coe = py_7i_coefficient_t()
        with open('./left_coe.dat', 'rb') as fp:
            data = fp.read()
            memmove(local_left_coe.buf, data, 1024)
            # print("read left coe")
        fp.close()

        local_right_coe = py_7i_coefficient_t()
        with open('./right_coe.dat', 'rb') as fp:
            data = fp.read()
            memmove(local_right_coe.buf, data, 1024)
            # print("read right coe")
        fp.close()

        left_buf_len = c_int(1024)
        flag_left_coe = b'biLeft'
        right_buf_len = c_int(1024)
        flag_right_coe = b'biRight'
        ret1 = self.sdk_dll_handle._7i_set_data(flag_left_coe, len(
            flag_left_coe), local_left_coe.buf, left_buf_len)
        ret2 = self.sdk_dll_handle._7i_set_data(flag_right_coe, len(
            flag_right_coe), local_right_coe.buf, right_buf_len)
        print("_7i_set_data: L %d" % (ret1))
        print("_7i_set_data: R %d" % (ret2))

        # Notes:
        # If you want to save the calibration coefficients as a file or
        # read the calibration coefficients from a local file, you can use the code below.
        # Save the coefficients as a file ==============================================================================
        # if 0 == ret1:
        #     res = bytearray(1024)
        #     ptr = (c_ubyte * 1024).from_buffer(res)
        #     memmove(ptr, left_coe.buf, 1024)
        #     with open('./left_coe.dat', 'wb') as fp:
        #         for i in ptr:
        #             s = struct.pack('B', i)
        #             fp.write(s)
        #     fp.close()
        #
        # if 0 == ret2:
        #     res = bytearray(1024)
        #     ptr = (c_ubyte * 1024).from_buffer(res)
        #     memmove(ptr, right_coe.buf, 1024)
        #     with open('./right_coe.dat', 'wb') as fp:
        #         for i in ptr:
        #             s = struct.pack('B', i)
        #             fp.write(s)
        #     fp.close()

        #  Read coefficients from a local file =========================================================================
        # local_left_coe = py_7i_coefficient_t()
        # with open('./left_coe.dat', 'rb') as fp:
        #     data = fp.read()
        #     memmove(local_left_coe.buf, data, 1024)
        # fp.close()
        #
        # local_right_coe = py_7i_coefficient_t()
        # with open('./right_coe.dat', 'rb') as fp:
        #     data = fp.read()
        #     memmove(local_right_coe.buf, data, 1024)
        # fp.close()
