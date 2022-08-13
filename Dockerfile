FROM luxonis/depthai-library:v2.17.3.0

RUN apt install -y feh
COPY ./ .
RUN python3 install_requirements.py

WORKDIR /depthai
