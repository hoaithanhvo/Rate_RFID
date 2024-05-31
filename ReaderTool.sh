#!/bin/bash

echo "Launching NIDEC RFID Sensing Gate..."

cd /home/ru224/Production_AssignLocation/dist/Main/

while 'true'
do
	./Main
	sleep 1
done

exit 0
