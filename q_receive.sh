#!/bin/sh

#queue="https://sqs.us-east-1.amazonaws.com/238500502456/diode"
# queue="https://sqs.us-east-1.amazonaws.com/238500502456/diode-test.fifo"
queue=https://sqs.us-east-1.amazonaws.com/458358814065/new-object-queue
opts="--wait-time-seconds 10 --max-number-of-messages 10"

while [ 1 -eq 1 ]
do
	mesg=$(aws sqs receive-message --queue-url $queue $opts)
	echo $mesg
	
	# body=$(echo $mesg | jq --raw-output '.Messages[].Body' )

	if [ $? -ne 0 ]
	then
		exit
	fi

done
