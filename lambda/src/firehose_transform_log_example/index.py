from __future__ import print_function
import json
import os
import traceback
import boto3
import logging
import base64
import zlib
from datetime import datetime, timezone
from flatten_json import flatten

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def add_field_if_doesnt_exist(obj, fieldname_str):
  # Check if the field exists
  if fieldname_str not in obj:
    # Add the field with an empty string value
    obj[fieldname_str] = ''
  return obj

def handler(event, context):
  output = []
  events_counter = 0
  error_counter = 0
  for record in event['records']:
    payload = base64.b64decode(record["data"])
    decompressed_payload = zlib.decompress(payload, 16+zlib.MAX_WBITS)

    # Decode the byte string to Unicode
    unicode_payload = decompressed_payload.decode('utf-8')
    
    # Parse the Unicode string as JSON
    json_obj = json.loads(unicode_payload)

    logger.info("cloudwatch record: {}".format(json_obj))
    
    logevents = json_obj['logEvents']
    logger.info("message type: {}".format(json_obj['messageType']))

    if len(logevents) > 0 and json_obj['messageType'] == 'DATA_MESSAGE':
      output_events = b''
      for logevent in logevents:
        try:
          events_counter+=1
          # log = logevent['message']
          # logger.debug("message: {}".format(log))
          
          parsedfields = logevent['extractedFields']
          logger.debug("parsed fields: {}".format(parsedfields))
          
          request = json.loads(parsedfields["request"])
          logger.debug("request: {}".format(request))

          datetime_object = datetime.strptime("{} {}".format(parsedfields["date"], parsedfields["time"]), '%Y-%m-%d %H:%M:%S,%f')
          # iso_date = datetime_object.isoformat()
          dt_timestamp = datetime_object.timestamp()
          new_obj = {
            "date": parsedfields["date"],
            "time": parsedfields["time"].split(',')[0],
            "ts": dt_timestamp,
            "request": request,
          }
          output_data = flatten(new_obj)

          #change this field to a string.. causing too many problems.
          output_data['request_context_user_id'] = str(output_data['request_context_user_id'])

          #Lets make request_event match bulk upload
          output_data["request_event"] = json.dumps(output_data["request_event"])
          
          #drop now empty request object (as request has been exploded!)
          output_data.pop('request', None)

          logger.info("output_data: {}".format(output_data))

          output_json_str = json.dumps(output_data).encode('utf-8') + b'\n'
          output_events += output_json_str
          # output_events.append(output_data)
        except ValueError as ve:
          error_counter += 1
          logger.error("Record has value error - dropping. ERR {}".format(ve))
        except Exception as e:
          error_counter += 1
          logger.error("UNKNOWN error occurred - dropping. ERR {}".format(e))

      output_record = {
        'recordId': record['recordId'],
        'result': 'Ok',
        'data': base64.b64encode(output_events).decode('utf-8')
      }
      output.append(output_record)

    else:
      output_record = {
        'recordId': record['recordId'],
        'result': 'Dropped'
      }
      output.append(output_record)

  logger.info('Successfully processed log events: {}'.format(events_counter))
  logger.info('Successfully processed records: {}'.format(len(event['records'])))
  logger.info('Number of errors encountered: {}'.format(error_counter))
  return {'records': output}