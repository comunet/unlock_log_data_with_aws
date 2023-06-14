#!/bin/sh
echo "Starting script to upload last Log Rotate file to S3"
echo "File name is: $1"
BUCKET="my-bucket-name-for-log-backups"
REGION="ap-southeast-2"
FORMAT=`date "+%Y%m%d"` 
FILENAME="$1.log-$FORMAT"
FILE="/home/ubuntu/data/logs/rotated/$1/$FILENAME"
aws s3 cp "$FILE" "s3://$BUCKET/rotated/${1}_log/$FILENAME" --region $REGION
