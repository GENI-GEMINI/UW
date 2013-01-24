SLICENAME=$1
while [[ 1 ]]
do
	date
	STATUS=0
	echo "Checking GEMINI Slice Status"
	./gdesktop-opstatus.py -n $SLICENAME;
	STATUS=$?
	if [ $STATUS -eq 0 ];then
		echo "Starting GEMINI Slice Initialization"
		./gdesktop-init.py -n $SLICENAME;
	else
		echo "Slice is not ready yet"
		exit 1;
	fi
	STATUS=$?
	if [ $STATUS -eq 0 ];then
		echo "Starting GEMINI Slice Instrumentization"
		./gdesktop-instrumentize.py -n $SLICENAME;
		date
		break;
	else
		exit 1;
	fi
done
