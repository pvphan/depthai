import cv2
import depthai as dai
import numpy as np


def main():
    pipeline = dai.Pipeline()
    camRgb = createCamRgb(pipeline)
    camLeft = createCamMono(pipeline, "left")
    camRight = createCamMono(pipeline, "right")

    device_info = dai.DeviceInfo()
    device_info.state = dai.XLinkDeviceState.X_LINK_BOOTLOADER
    device_info.desc.protocol = dai.XLinkProtocol.X_LINK_TCP_IP
    device_info.desc.name = "192.168.0.225"

    with dai.Device(pipeline, device_info) as device:
        qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
        qLeft = device.getOutputQueue(name="left", maxSize=4, blocking=False)
        qRight = device.getOutputQueue(name="right", maxSize=4, blocking=False)
        while True:
            frameRGB = qRgb.get().getCvFrame()
            frameLeft = qLeft.get().getCvFrame()
            frameRight = qRight.get().getCvFrame()
            frameRGBScaled = cv2.resize(frameRGB, frameLeft.shape[:2][::-1])
            print(frameLeft.shape, frameRight.shape, frameRGBScaled.shape)
            cv2.imshow("left-right", np.hstack((frameLeft, frameRight)))
            if cv2.waitKey(1) == ord('q'):
                break

def createCamRgb(pipeline):
    camRgb = pipeline.createColorCamera()
    camRgb.setResolution(
            dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    focusValue = 135
    camRgb.initialControl.setManualFocus(focusValue)
    camRgb.setInterleaved(False)
    camRgb.setBoardSocket(dai.CameraBoardSocket.RGB)
    #camRgb.setIspScale(1, 3)
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
            dai.MonoCameraProperties.SensorResolution.THE_800_P)
    fps = 30
    camMono.setFps(fps)
    xoutMono.setStreamName(side)
    camMono.out.link(xoutMono.input)
    return camMono


if __name__ == "__main__":
    main()
