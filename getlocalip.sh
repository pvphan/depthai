#/bin/bash
ifconfig en0 | grep inet | awk '$1=="inet" {print $2}'
