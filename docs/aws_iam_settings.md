# AWS IAM Permissions

In order to use Ankify with AWS Polly, you need to create an IAM user with the following permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PollyTTS",
            "Effect": "Allow",
            "Action": "polly:SynthesizeSpeech",
            "Resource": "*"
        }
    ]
}
```

Add via AWS Console: **IAM → Users → your user → Add permissions → Create inline policy → JSON tab** → paste the relevant policy above.

Alternatively, you can simply select Polly permissions in the IAM user creation wizard.

Then, create the key for that user and use it in the Ankify configuration.