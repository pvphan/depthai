import cv2
import depthai as dai
import numpy as np


def main():
    pipeline = dai.Pipeline()

    camRgb = pipeline.createColorCamera()

    xoutRgb = pipeline.createXLinkOut()
    xoutRgb.setStreamName("rgb")
    camRgb.preview.link(xoutRgb.input)

    device_info = dai.DeviceInfo()
    device_info.state = dai.XLinkDeviceState.X_LINK_BOOTLOADER
    device_info.desc.protocol = dai.XLinkProtocol.X_LINK_TCP_IP
    device_info.desc.name = "192.168.0.225"

    with dai.Device(pipeline, device_info) as device:
        qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
        #qLeft = device.getOutputQueue(name="left", maxSize=4, blocking=False)
        #qRight = device.getOutputQueue(name="right", maxSize=4, blocking=False)
        while True:
            cv2.imshow("rgb", qRgb.get().getCvFrame())
            #leftRight = np.hstack((qLeft.get().getCvFrame(), qRight.get().getCvFrame()))
            #cv2.imshow("left-right", leftRight)
            if cv2.waitKey(1) == ord('q'):
                break


if __name__ == "__main__":
    main()
