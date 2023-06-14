
# Unlocking your Log Data with AWS

This project includes sample code for using native AWS Services to capture and report on Application Log data captured in Virtual Machines (EC2) or containers in AWS.

These samples can be followed in-line with blog post located here:
[https://www.linkedin.com/pulse/liberate-your-log-data-from-storage-hell-damien-coyle]

- [Unlocking your Log Data with AWS](#unlocking-your-log-data-with-aws)
  - [1 Configuring CloudWatch Agent on to collect log data from Application Server](#1-configuring-cloudwatch-agent-on-to-collect-log-data-from-application-server)
    - [1.1 Create an AWS User for saving CloudWatch Config to SSM](#11-create-an-aws-user-for-saving-cloudwatch-config-to-ssm)
    - [1.2 Install CloudWatch Agent on EC2 (Ubuntu used as example)](#12-install-cloudwatch-agent-on-ec2-ubuntu-used-as-example)
  - [2. Create a Lambda to be used for Firehose Transformation](#2-create-a-lambda-to-be-used-for-firehose-transformation)
  - [3. Create a new Kinesis Firehose delivery stream](#3-create-a-new-kinesis-firehose-delivery-stream)
  - [4. Create new CloudWatchLog Subscription from Log Group `my-apache-error-log` to Firehose Delivery Stream](#4-create-new-cloudwatchlog-subscription-from-log-group-my-apache-error-log-to-firehose-delivery-stream)
  - [5. Setup a Glue Database and Table to use as a Parquet Schema](#5-setup-a-glue-database-and-table-to-use-as-a-parquet-schema)
  - [6. Update Firehose Delivery Stream and Enable convert to Parquet](#6-update-firehose-delivery-stream-and-enable-convert-to-parquet)
  - [7. Setup Log Rotate and auto backup to S3](#7-setup-log-rotate-and-auto-backup-to-s3)
  - [8. Create a Glue Crawler to parse outputed Firehose Data](#8-create-a-glue-crawler-to-parse-outputed-firehose-data)
  - [9. Test Query your new data](#9-test-query-your-new-data)
  - [10. Contact](#10-contact)


## 1 Configuring CloudWatch Agent on to collect log data from Application Server

### 1.1 Create an AWS User for saving CloudWatch Config to SSM
1. In IAM, create user with programmatic Access Key + Secret Key (download for reference)
2. Add Managed Policy `arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy` (CloudWatchAgentServerPolicy)
3. Create inline policy with:
```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": "ssm:PutParameter",
            "Resource": "arn:aws:ssm:REGION:ACCOUNT_ID:parameter/AmazonCloudWatch-*"
        }
    ]
}
```

### 1.2 Install CloudWatch Agent on EC2 (Ubuntu used as example)
1. Run commands
```
sudo wget https://s3.amazonaws.com/amazoncloudwatch-agent/debian/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i -E ./amazon-cloudwatch-agent.deb
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard
```
1. In wizard go through all steps, choose default answer up until question 'Do you want to specify any additional log files to monitor'

Add a Logs Path and Log Group for all log files you want to have monitored
i.e.

Add Logs Path:
```
/var/log/apache2/logs/error.log
```
With Log group:
```
my-apache-error-log
```
Repeat for all logs you want to capture

2. Select Yes to save to SSM. Set name `AmazonCloudWatch-my-agent-config` for the parameter store name
3. Enter the Access Key and Secret Key created earlier in (5.1)

4. Fix Agent to works with Collectd
```
sudo mkdir -p /usr/share/collectd/
sudo touch /usr/share/collectd/types.db
```
5. Start CloudWatch Agent
```
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c file:/opt/aws/amazon-cloudwatch-agent/bin/config.json -s
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -m ec2 -a status
```

## 2. Create a Lambda to be used for Firehose Transformation
1. Compile your local lambda requirements
```
cd lambda/src/firehose_transform_log_example
pip install -r requirements.txt
```
2. Manually zip up the contents of the `lambda/src/firehose_transform_log_example` folder
3. In the AWS Lambda Service, create a new Python Lambda uploading the zip file

## 3. Create a new Kinesis Firehose delivery stream
1. Navigate to Kinesis Firehose service
2. Create a new Firehose Delivery Stream to S3
3. Create a new bucket for your delivery stream to store results i.e. `myapp-streaming-logs`
4. To create a nice partition on your log data set a `data_output_prefix` and `error_output_prefix` similar to below:

data_output_prefix:
```
"output/myapp_logs/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
```
error_output_prefix:
```
"processing_error/myapp_logs/!{firehose:error-output-type}/!{timestamp:yyyy/MM/dd}/!{firehose:random-string}/"
```
5. Enable Transformation with Lambda and select your Firehose Transformation lambda.


## 4. Create new CloudWatchLog Subscription from Log Group `my-apache-error-log` to Firehose Delivery Stream
1. Navigate to CloudWatch click on Log group `my-apache-error-log`
2. Actions >> Subscription filters >> Create Kinesis Firehose subscription filter
   Use a filter that best parses your log file. For example if you have a space-delimited log file you could use a filter like:
   ```
   [date, time, log_level, type_id, log_type, auth_user, ip_address, file, blank, request]
   ```
   To capture individual fields to save processing time/effort in your lambda.
3. Create a new Select Kinesis Firehose delivery stream
4. Select the Kinesis Firehose Role created in step 5 (you may need additional rights to for CloudWatch to assume this role)

## 5. Setup a Glue Database and Table to use as a Parquet Schema
1. Navigate to AWS Glue and create a glue catalogue/database named `log-schemas`
2. Create a new table with schema that matches your flattened JSON payload of type Parquet named `log-apache2-errors-parquet`

## 6. Update Firehose Delivery Stream and Enable convert to Parquet
1. Navigate back to your firehose delivery stream and enable convert to Parquet feature.
2. Select you glue catalogue (`log-schemas`) and table (`log-apache2-errors-parquet`) for Firehose to convert the payload to match


## 7. Setup Log Rotate and auto backup to S3
[https://www.digitalocean.com/community/tutorials/how-to-manage-logfiles-with-logrotate-on-ubuntu-20-04]

Create a new configuration for rotating lift logs
1. Create folders (update to be suitable for your log file)
```
mkdir /home/ubuntu/data/logs/rotated
mkdir /home/ubuntu/data/logs/rotated/apache2_errors/
```
1. Create and Copy a LastAction script to the server
Make directory for it and give copy + execute permissions
```
sudo mkdir /etc/my-logrotate
sudo chmod 777 /etc/my-logrotate
```
Use WinSCP. Copy file `/scripts/logrotate/lastaction_upload_to_s3.sh` to `/etc/my-logrotate`


3. Setup Log Rotate for your Log File and Upload to S3
```
sudo nano /etc/logrotate.d/my-app-log
```
With contents:
```
/var/log/apache2/logs/error.log {
  daily
  missingok
  rotate 14
  notifempty
  dateext
  create 0640 ubuntu ubuntu
  copytruncate
  sharedscripts
  dateformat -%Y%m%d
  olddir /home/ubuntu/data/logs/rotated/apache2_errors/
  lastaction
    /etc/lift-logrotate/lastaction_upload_to_s3.sh apache2_errors
  endscript
}
```
Exit and save file.


4. Check Log Rotation setup correctly with:
```
sudo logrotate /etc/logrotate.conf --debug
```
5. Check the status of log rotate with:
```
sudo cat /var/lib/logrotate/status
```
You can also manually edit this status and change a date to test..
```
sudo nano /var/lib/logrotate/status
```
6. Manually Run Logrotate... 
IN DEBUG MODE
```
sudo /usr/sbin/logrotate -d /etc/logrotate.conf
```
IN REAL MODE
```
sudo /usr/sbin/logrotate /etc/logrotate.conf
```
AND WITH FORCE... which sometimes is needed to wake the service up to new log files
```
sudo /usr/sbin/logrotate -f /etc/logrotate.conf
```

## 8. Create a Glue Crawler to parse outputed Firehose Data
1. Navigate to AWS Glue
1. Create another Glue Catalogue for your final Firehose Data `streaming-logs-db`
2. Setup a new Crawler pointed to your S3 bucket (`myapp-streaming-logs`) and outputting to your new catalogue `streaming-logs-db`.
   The build in crawler classifier should support your parquet output by default.
3. Run the crawler and check that a new table is automatically detected.

## 9. Test Query your new data
1. Navigate to Athena Service
2. Setup a workspace (if you have not already done so you will need an S3 Bucket for Athena Results)
3. Select your output catalogue `streaming-logs-db` and table and check that query returns results


## 10. Contact
For more information please contact:
* **Damien Coyle (Comunet Pty Ltd)** - *Initial work MAY 2023* - [Comunet](https://www.comunet.com.au)
