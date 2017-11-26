import picamera
import boto3
import json
import os
import datetime
import decimal
import logging
from ConfigParser import SafeConfigParser
from boto3.dynamodb.conditions import Key, Attr # To allow scan of DynamoDB

########################################################
#Read in Application Settings from Config File
parser = SafeConfigParser()

parser.read('/home/pi/Project/live/locateme/locateme.cfg')
installDir = parser.get('settings', 'installdir')
deviceLocation = parser.get('settings', 'location')
BUCKET = parser.get('settings', 'BUCKET')
KEY = parser.get('settings', 'KEY')
COLLECTION = parser.get('settings', 'COLLECTION')
pollyVoice = parser.get('settings', 'pollyvoice')

########################################################
#Set up Logging Configuration
logging.basicConfig(filename='/var/log/locateme.log',
    format='%(asctime)s %(message)s',
    level=logging.DEBUG)
logging.info('###########################################################################\n                        Logging Starting')

#######################
########################################################
# Take photo
camera = picamera.PiCamera()
camera.resolution = (1640, 1232)
#camera.resolution = (1280, 720)
#camera.capture('/home/pi/Project/live/locateme/' + 'photo.jpg')
camera.capture(installDir + '/photo.jpg')
logging.info('Photo taken')

########################################################
# Upload Photo to AWS S3
# Create an S3 client
s3 = boto3.client('s3')


# Uploads the given file using a managed uploader, which will split up large
# files automatically and upload parts in parallel.
#s3.upload_file('/home/pi/Project/live/locateme/photo.jpg', BUCKET, 'photo.jpg')
s3.upload_file(installDir + '/photo.jpg', BUCKET, 'photo.jpg')
logging.info('Photo uploaded to S3')

########################################################
# Identify Face in Photo using AWS Rekognition
def search_faces_by_image(bucket, key, collection, threshold=80, region="eu-west-1"):
	rekognition = boto3.client("rekognition", region)
	response = rekognition.search_faces_by_image(
		Image={
			"S3Object": {
				"Bucket": bucket,
				"Name": key,
			}
		},
		CollectionId=collection,
		FaceMatchThreshold=threshold,
	)
	return response['FaceMatches']
record = search_faces_by_image(BUCKET, KEY, COLLECTION)
logging.info('Photo matched on AWS Rekognise')

#Select first response record for matched Faces
matchedface = record[0]
#Select face details from first record
face = matchedface['Face']
#Select the ExternalImageID field for name of person
matchedfacename = face['ExternalImageId']
print face
print ('')
print matchedfacename
print "  ImageId : {}".format(face['ExternalImageId'])
print ('')
logging.info('Photo matched as ' + matchedfacename)

########################################################
#Generate the mp3 file using AWS Polly
polly = boto3.client('polly')
currentTime = datetime.datetime.now()
currentTime.hour

if currentTime.hour < 12:
    outputtext = "Good morning" + matchedfacename
elif 12 <= currentTime.hour < 18:
    outputtext = "Good afternoon" + matchedfacename
else:
    outputtext = "Good evening" + matchedfacename


resp = polly.synthesize_speech(OutputFormat='mp3',
        Text=outputtext,
        VoiceId=pollyVoice)
logging.info('AWS Polly request sent')
		
thebytes = resp['AudioStream'].read()
#thefile = open('/home/pi/Project/live/locateme/output.mp3', 'wb')
thefile = open(installDir + '/output.mp3', 'wb')
thefile.write(thebytes)
thefile.close()
logging.info('mp3 file created from AWS Polly response')

#Play the generated speech from AWS Polly
#os.system('mpg321 /home/pi/Project/live/locateme/output.mp3')
os.system('mpg321 ' + installDir + '/output.mp3')
logging.info('mp3 file played')

########################################################
#Determine UserID from matched face name
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('users')
pe = "UserID"

response = table.scan(
	FilterExpression=Key('FirstName').eq(matchedfacename),
	ProjectionExpression=pe
)
item = response['Items']
userIDNumber = item[0]['UserID']

########################################################
#Determine LocationID from Location Name
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('locations')
pe = "locationID"

response = table.scan(
	FilterExpression=Key('locationName').eq(deviceLocation),
	ProjectionExpression=pe
)
item = response['Items']
locationIDNumber = item[0]['locationID']

###########################################################
#Determine the person's emotions
FEATURES_BLACKLIST = ("Landmarks", "Emotions", "Pose", "Quality", "BoundingBox", "Confidence")

def detect_faces(bucket, key, attributes=['ALL'], region="eu-west-1"):
	rekognition = boto3.client("rekognition", region)
	response = rekognition.detect_faces(
	    Image={
			"S3Object": {
				"Bucket": bucket,
				"Name": key,
			}
		},
	    Attributes=attributes,
	)
	return response['FaceDetails']

for face in detect_faces(BUCKET, KEY):
	for emotion in face['Emotions']:
		test = "{Confidence}".format(**emotion)
		if (float(test) > 80):
			emotionType = "{Type}".format(**emotion)
		else:
			emotionType = "UNKNOWN"
logging.info('Emotion detected')			
			
###########################################################
#Log the details to DynamoDB
currentTime = datetime.datetime.utcnow().isoformat()

# Get the service resource.
dynamodb = boto3.resource('dynamodb')

table = dynamodb.Table('historical')
table.put_item(
   Item={
        'date_time': currentTime,
        'location_id': locationIDNumber,
        'user_id': userIDNumber
    }
)

###########################################################
#Update status table on DynamoDB
table = dynamodb.Table('status')
table.update_item(
	Key={
        'userID': userIDNumber
    },
    UpdateExpression="set locationID = :l, emotion = :e",
    ExpressionAttributeValues={
        ':l': decimal.Decimal(locationIDNumber),
		':e': emotionType
    },
    ReturnValues="UPDATED_NEW"
)



##################################################################

if emotionType == 'HAPPY':
	outputtext = "You appear to bee" + emotionType
elif emotionType == 'SAD':
	outputtext = "You appear to bee" + emotionType
elif emotionType == 'ANGRY':
	outputtext = "You appear to bee" + emotionType
elif emotionType == 'CONFUSED':
	outputtext = "You appear to bee" + emotionType
elif emotionType == 'DISGUSTED':
	outputtext = "You appear to bee" + emotionType
elif emotionType == 'SURPRISED':
	outputtext = "You appear to bee" + emotionType
elif emotionType == 'CALM':
	outputtext = "You appear to bee" + emotionType
else:
	outputtext = "How are you?"
	
resp = polly.synthesize_speech(OutputFormat='mp3',
        Text=outputtext,
        VoiceId=pollyVoice)
logging.info('AWS Polly request sent')
		
thebytes = resp['AudioStream'].read()
thefile = open('/home/pi/Project/live/locateme/output_emotion.mp3', 'wb')
thefile = open(installDir + '/output_emotion.mp3', 'wb')
thefile.write(thebytes)
thefile.close()
logging.info('mp3 file created from AWS Polly response')

#Play the generated speech from AWS Polly
#os.system('mpg321 /home/pi/Project/live/locateme/output_emotion.mp3')
os.system('mpg321 ' + installDir + '/output_emotion.mp3')
logging.info('mp3 file played')
