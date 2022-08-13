FROM luxonis/depthai-library:v2.17.3.0

RUN apt install -qqy x11-apps feh

WORKDIR /depthai
