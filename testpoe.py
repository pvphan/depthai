import time

import cv2
import depthai as dai
import numpy as np


def main():
    pipeline = dai.Pipeline()
    camRgb = createCamRgb(pipeline)
    camLeft = createCamMono(pipeline, "left")
    camRight = createCamMono(pipeline, "right")

    device_info = dai.DeviceInfo("192.168.20.3")
    device_info.state = dai.XLinkDeviceState.X_LINK_BOOTLOADER
    device_info.desc.protocol = dai.XLinkProtocol.X_LINK_TCP_IP

    with dai.Device(pipeline, device_info) as device:
        qRgb = device.getOutputQueue(name="rgb", maxSize=1, blocking=True)
        qLeft = device.getOutputQueue(name="left", maxSize=1, blocking=True)
        qRight = device.getOutputQueue(name="right", maxSize=1, blocking=True)
        while True:
            ts = time.time()
            frameRGB = qRgb.get().getCvFrame()
            t1 = time.time()
            frameLeft = qLeft.get().getCvFrame()
            t2 = time.time()
            frameRight = qRight.get().getCvFrame()
            t3 = time.time()
            frameRGBScaled = cv2.resize(frameRGB, frameLeft.shape[:2][::-1])
            t4 = time.time()
            # print(time.time(), frameLeft.shape, frameRight.shape, frameRGBScaled.shape)
            print(f"{t1-ts:0.3f}, {t2-t1:0.3f}, {t3-t2:0.3f}, {t4-t3:0.3f}")
            cv2.imshow("rgb-left-right",
                np.hstack((
                    frameRGBScaled,
                    cv2.cvtColor(frameLeft, cv2.COLOR_GRAY2BGR),
                    cv2.cvtColor(frameRight, cv2.COLOR_GRAY2BGR),
                ))
            )
            if cv2.waitKey(1) == ord('q'):
                break


def updateFrame(frame, queue):
    frame = queue.get().getCvFrame()


def createCamRgb(pipeline):
    camRgb = pipeline.createColorCamera()
    camRgb.setResolution(
            dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    focusValue = 100
    camRgb.initialControl.setManualFocus(focusValue)
    camRgb.setInterleaved(False)
    camRgb.setBoardSocket(dai.CameraBoardSocket.RGB)
    camRgb.initialControl.setManualFocus(focusValue)
    fps = 30
    camRgb.setFps(fps)
    xoutRgb = pipeline.createXLinkOut()
    xoutRgb.setStreamName("rgb")
    camRgb.isp.link(xoutRgb.input)
    return camRgb


def createCamMono(pipeline, side):
    camMono = pipeline.createMonoCamera()
    xoutMono = pipeline.createXLinkOut()
    camMono.setBoardSocket(dai.CameraBoardSocket.LEFT
            if side == "left" else dai.CameraBoardSocket.RIGHT)
    camMono.setResolution(
            dai.MonoCameraProperties.SensorResolution.THE_400_P)
    fps = 30
    camMono.setFps(fps)
    xoutMono.setStreamName(side)
    camMono.out.link(xoutMono.input)
    return camMono


if __name__ == "__main__":
    main()
