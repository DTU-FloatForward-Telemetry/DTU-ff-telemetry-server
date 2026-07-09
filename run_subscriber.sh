#!/bin/bash
cd ~/Desktop/ff_server
source ff-env/bin/activate
python3 -u src/mqtt_subscriber_real_test.py 2>&1 | tee race_log.txt
