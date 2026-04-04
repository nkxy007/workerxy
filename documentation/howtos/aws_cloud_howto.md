# AWS CLI on CentOS Stream 10

## Install

```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

Verify:
```bash
aws --version
```

---

## Configure

```bash
aws configure
```

You'll be prompted for:

```
AWS Access Key ID:      your-access-key-id
AWS Secret Access Key:  your-secret-access-key
Default region name:    us-east-1
Default output format:  json
```

Credentials are stored in `~/.aws/credentials`, config in `~/.aws/config`.

---

## Multiple Profiles

```bash
aws configure --profile myprofile
```

Use a profile:
```bash
aws s3 ls --profile myprofile
```

---

## Getting Your Keys

Go to **AWS Console → IAM → Users → your user → Security credentials → Create access key**.