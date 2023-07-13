from datetime import timedelta
import logging
import math
from collections import defaultdict
from typing import Dict, Optional, List, Union, Tuple

import depthai as dai
import numpy as np
from depthai_sdk.classes import DetectionPacket, TrackerPacket
from depthai_sdk.classes.packets import TrackingDetection
from depthai_sdk.oak_outputs.xout.xout_base import StreamXout
from depthai_sdk.oak_outputs.xout.xout_nn import XoutNnResults
from depthai_sdk.tracking import KalmanFilter
from depthai_sdk.visualize.bbox import BoundingBox

class TrackedObject:
    def __init__(self, baseline: float, focal: float, apply_kalman: bool, calculate_speed: bool):
        # Point
        self.kalman_3d: KalmanFilter = None
        # BBox
        self.kalman_2d: KalmanFilter = None

        self.previous_detections: List[TrackingDetection] = []
        self.blacklist = False
        self.lost_counter = 0

        self.baseline = baseline
        self.focal = focal
        self.apply_kalman = apply_kalman
        self.calculate_speed = calculate_speed

    def new_tracklet(self, tracklet: dai.Tracklet, ts: timedelta, color: Tuple, label: str):
        is_3d = self._is_3d(tracklet)
        tracking_det = TrackingDetection(
            img_detection=tracklet.srcImgDetection,
            label_str=label,
            confidence=tracklet.srcImgDetection.confidence,
            color=color,
            bbox=BoundingBox(tracklet.srcImgDetection),
            angle=None,
            tracklet=tracklet,
            ts=ts,
            filtered_2d=self._calc_kalman_2d(tracklet,ts) if self.apply_kalman else None,
            filtered_3d=self._calc_kalman_3d(tracklet,ts) if self.apply_kalman and is_3d else None,
            speed=0.0, speed_kmph=0.0, speed_mph=0.0
            )
        self.previous_detections.append(tracking_det)
        # Calc speed should be called after adding new TrackingDetection to self.previous_detections
        speed_mps = self.calc_speed() if (self.calculate_speed and is_3d) else 0.0
        tracking_det.speed = speed_mps
        tracking_det.speed_kmph=speed_mps * 3.6
        tracking_det.speed_mph=speed_mps * 2.236936

    def calc_speed(self) -> float:
        """
        Should be called after adding new TrackingDetection to self.previous_detections
        """
        def get_coords(det) -> dai.Point3f:
            return det.filtered_3d or \
                     det.tracklet.spatialCoordinates
        def get_dist(p1: dai.Point3f, p2: dai.Point3f) -> float:
            return np.sqrt((p2.x - p1.x) ** 2 + (p2.y - p1.y) ** 2 + (p2.z - p1.z) ** 2) / 1000

        speeds = []
        for i in range(len(self.previous_detections) - 1):
            d1 = self.previous_detections[i]
            d2 = self.previous_detections[i + 1]
            distance = get_dist(get_coords(d1), get_coords(d2))
            time = (d2.ts - d1.ts).total_seconds()
            speeds.append(distance / time)

        if len(speeds) == 0:
            return 0.0

        window_size = 3
        window = np.hanning(window_size)
        window /= window.sum()

        print('window', speeds, window)

        smoothed = np.convolve(speeds, window, mode='same')
        print('smoothed', np.mean(smoothed))
        return np.mean(smoothed)

    def _is_3d(self, tracklet: dai.Tracklet) -> bool:
        return tracklet.spatialCoordinates.x != 0.0 or \
               tracklet.spatialCoordinates.y != 0.0 or \
               tracklet.spatialCoordinates.z != 0.0

    def _calc_kalman_3d(self, tracklet: dai.Tracklet, ts: timedelta) -> Union[None, dai.Point3f]:
        print('a')
        x_space = tracklet.spatialCoordinates.x
        y_space = tracklet.spatialCoordinates.y
        z_space = tracklet.spatialCoordinates.z
        meas_vec_space = np.array([[x_space], [y_space], [z_space]])
        meas_std_space = z_space ** 2 / (self.baseline * self.focal)

        if self.kalman_3d is None:
            self.kalman_3d = KalmanFilter(10, 0.1, meas_vec_space, ts)
            return None
        print('b')

        dt = (ts - self.kalman_3d.time).total_seconds()
        self.kalman_3d.predict(dt)
        self.kalman_3d.update(meas_vec_space)
        self.kalman_3d.time = ts
        self.kalman_3d.meas_std = meas_std_space
        vec_space = self.kalman_3d.x
        print('c')
        print('vec_space', vec_space)
        p =dai.Point3f(vec_space[0], vec_space[1], vec_space[2])
        print(p)
        return p

    def _calc_kalman_2d(self, tracklet: dai.Tracklet, ts: timedelta) -> Union[None, BoundingBox]:
        print('1')
        bb = BoundingBox(tracklet.srcImgDetection)
        x_mid, y_mid = bb.get_centroid().to_tuple()

        meas_vec_bbox = np.array([[x_mid], [y_mid], [bb.width], [bb.height]])

        if self.kalman_2d is None:
            self.kalman_2d = KalmanFilter(10, 0.1, meas_vec_bbox, ts)
            return None

        dt = (ts - self.kalman_2d.time).total_seconds()

        self.kalman_2d.predict(dt)
        self.kalman_2d.update(meas_vec_bbox)
        self.kalman_2d.time = ts
        vec_bbox = self.kalman_2d.x

        return BoundingBox([
            vec_bbox[0] - vec_bbox[2] / 2,
            vec_bbox[0] + vec_bbox[2] / 2,
            vec_bbox[1] - vec_bbox[3] / 2,
            vec_bbox[1] + vec_bbox[3] / 2,
        ])

class XoutTracker(XoutNnResults):
    def __init__(self,
                 det_nn: 'NNComponent',
                 frames: StreamXout,
                 device: dai.Device,
                 tracklets: StreamXout,
                 bbox: BoundingBox,
                 apply_kalman: bool = False,
                 forget_after_n_frames: Optional[int] = None,
                 calculate_speed: bool = False,
                 ):
        """
        apply_kalman: Whether to apply kalman filter to tracklets
        forget_after_n_frames: If tracklet is lost for n frames, remove it from tracked_objects

        """
        super().__init__(det_nn, frames, tracklets, bbox)
        self.name = 'Object Tracker'
        self.__read_device_calibration(device)

        self.tracked_objects: Dict[int, TrackedObject] = {}

        self.apply_kalman = apply_kalman
        self.forget_after_n_frames = forget_after_n_frames
        self.calculate_speed = calculate_speed

    def package(self, msgs: Dict) -> TrackerPacket:
        tracklets: dai.Tracklets = msgs[self.nn_results.name]

        for tracklet in tracklets.tracklets:
            # If there is no id in self.tracked_objects, create new TrackedObject. This could happen if
            # TrackingStatus.NEW, or we removed it (too many lost frames)
            if tracklet.id not in self.tracked_objects:
                self.tracked_objects[tracklet.id] = TrackedObject(self.baseline, self.focal, self.apply_kalman,self.calculate_speed)

            if tracklet.status == dai.Tracklet.TrackingStatus.NEW:
                pass
            elif tracklet.status == dai.Tracklet.TrackingStatus.TRACKED:
                self.tracked_objects[tracklet.id].lost_counter = 0
            elif tracklet.status == dai.Tracklet.TrackingStatus.LOST:
                self.tracked_objects[tracklet.id].lost_counter += 1


            img_d = tracklet.srcImgDetection
            # When adding new tracklet, TrackletObject class will also perform filtering
            # and speed estimation
            self.tracked_objects[tracklet.id] \
                .new_tracklet(tracklet,
                            tracklets.getTimestamp(),
                            self.labels[img_d.label][1] if self.labels else (255, 255, 255),
                            self.labels[img_d.label][0] if self.labels else str(img_d.label)
                            )
            if tracklet.status == dai.Tracklet.TrackingStatus.REMOVED or \
                (self.forget_after_n_frames is not None and \
                self.forget_after_n_frames <= self.tracked_objects[tracklet.id].lost_counter):
                # Remove TrackedObject
                self.tracked_objects.pop(tracklet.id)

        packet = TrackerPacket(
            self.get_packet_name(),
            msgs[self.frames.name],
            tracklets,
            bbox=self.bbox,
        )

        for obj_id, tracked_obj in self.tracked_objects.items():
            if obj_id not in packet.tracklets:
                packet.tracklets[obj_id] = []
            for tracking_det in tracked_obj.previous_detections:
                packet.tracklets[obj_id].append(tracking_det)

        return packet

    def __read_device_calibration(self, device: dai.Device):
        calib = device.readCalibration()
        eeprom = calib.getEepromData()
        left_cam = calib.getStereoLeftCameraId()
        if left_cam != dai.CameraBoardSocket.AUTO and left_cam in eeprom.cameraData.keys():
            cam_info = eeprom.cameraData[left_cam]
            self.baseline = abs(cam_info.extrinsics.specTranslation.x * 10)  # cm -> mm
            fov = calib.getFov(calib.getStereoLeftCameraId())
            self.focal = (cam_info.width / 2) / (2. * math.tan(math.radians(fov / 2)))
        else:
            logging.warning("Calibration data missing, using OAK-D defaults")
            self.baseline = 75
            self.focal = 440
