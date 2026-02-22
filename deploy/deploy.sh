#!/bin/bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Aurea — one-shot EC2 deployment
# Usage: ./deploy/deploy.sh
# Requires: AWS CLI configured with hacklondon profile
# ─────────────────────────────────────────────────────────────────────────────

PROFILE="hacklondon"
REGION="us-east-1"
BUCKET="aurea-config-hacklondon"
ROLE_NAME="aurea-ec2-role"
INSTANCE_PROFILE="aurea-ec2-profile"
POLICY_NAME="aurea-s3-read"
INSTANCE_TYPE="t3.medium"
AMI_ID="ami-0c02fb55956c7d316"   # Amazon Linux 2023 us-east-1 (update if needed)
KEY_NAME="aurea-key"
SG_NAME="aurea-sg"
TAG="aurea-prod"

echo "=== [1/7] Creating S3 bucket and uploading .env ==="
aws s3 mb "s3://${BUCKET}" --region "${REGION}" --profile "${PROFILE}" 2>/dev/null || true
aws s3 cp backend/.env "s3://${BUCKET}/backend.env" \
    --profile "${PROFILE}" --region "${REGION}"
echo "    .env uploaded to s3://${BUCKET}/backend.env"

echo "=== [2/7] Creating IAM role for EC2 ==="
aws iam create-role \
    --role-name "${ROLE_NAME}" \
    --assume-role-policy-document '{
      "Version":"2012-10-17",
      "Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]
    }' \
    --profile "${PROFILE}" 2>/dev/null || echo "    Role already exists"

aws iam put-role-policy \
    --role-name "${ROLE_NAME}" \
    --policy-name "${POLICY_NAME}" \
    --policy-document "{
      \"Version\":\"2012-10-17\",
      \"Statement\":[{
        \"Effect\":\"Allow\",
        \"Action\":[\"s3:GetObject\"],
        \"Resource\":\"arn:aws:s3:::${BUCKET}/*\"
      }]
    }" \
    --profile "${PROFILE}"

aws iam create-instance-profile \
    --instance-profile-name "${INSTANCE_PROFILE}" \
    --profile "${PROFILE}" 2>/dev/null || echo "    Instance profile already exists"

aws iam add-role-to-instance-profile \
    --instance-profile-name "${INSTANCE_PROFILE}" \
    --role-name "${ROLE_NAME}" \
    --profile "${PROFILE}" 2>/dev/null || echo "    Role already attached"

echo "    Waiting for instance profile to propagate..."
sleep 10

echo "=== [3/7] Creating key pair ==="
aws ec2 create-key-pair \
    --key-name "${KEY_NAME}" \
    --query "KeyMaterial" \
    --output text \
    --profile "${PROFILE}" \
    --region "${REGION}" > "${KEY_NAME}.pem" 2>/dev/null || echo "    Key pair already exists"
chmod 400 "${KEY_NAME}.pem" 2>/dev/null || true
echo "    Key saved to ${KEY_NAME}.pem"

echo "=== [4/7] Creating security group ==="
VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=isDefault,Values=true" \
    --query "Vpcs[0].VpcId" --output text \
    --profile "${PROFILE}" --region "${REGION}")

SG_ID=$(aws ec2 create-security-group \
    --group-name "${SG_NAME}" \
    --description "Aurea production security group" \
    --vpc-id "${VPC_ID}" \
    --query "GroupId" --output text \
    --profile "${PROFILE}" --region "${REGION}" 2>/dev/null) || \
SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=${SG_NAME}" \
    --query "SecurityGroups[0].GroupId" --output text \
    --profile "${PROFILE}" --region "${REGION}")

# Allow HTTP (80), HTTPS (443), SSH (22)
for PORT in 22 80 443; do
    aws ec2 authorize-security-group-ingress \
        --group-id "${SG_ID}" \
        --protocol tcp --port "${PORT}" --cidr "0.0.0.0/0" \
        --profile "${PROFILE}" --region "${REGION}" 2>/dev/null || true
done
echo "    Security group: ${SG_ID}"

echo "=== [5/7] Launching EC2 t3.medium instance ==="
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id "${AMI_ID}" \
    --instance-type "${INSTANCE_TYPE}" \
    --key-name "${KEY_NAME}" \
    --security-group-ids "${SG_ID}" \
    --iam-instance-profile Name="${INSTANCE_PROFILE}" \
    --user-data file://deploy/userdata.sh \
    --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":20,"VolumeType":"gp3"}}]' \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${TAG}}]" \
    --query "Instances[0].InstanceId" --output text \
    --profile "${PROFILE}" --region "${REGION}")

echo "    Instance launched: ${INSTANCE_ID}"

echo "=== [6/7] Waiting for instance to be running ==="
aws ec2 wait instance-running \
    --instance-ids "${INSTANCE_ID}" \
    --profile "${PROFILE}" --region "${REGION}"

PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids "${INSTANCE_ID}" \
    --query "Reservations[0].Instances[0].PublicIpAddress" --output text \
    --profile "${PROFILE}" --region "${REGION}")

echo "=== [7/7] Done ==="
echo ""
echo "  Instance ID : ${INSTANCE_ID}"
echo "  Public IP   : ${PUBLIC_IP}"
echo "  App URL     : http://${PUBLIC_IP}"
echo "  SSH         : ssh -i ${KEY_NAME}.pem ec2-user@${PUBLIC_IP}"
echo ""
echo "  The instance is bootstrapping — allow ~3-4 minutes for Docker build."
echo "  Monitor progress: ssh -i ${KEY_NAME}.pem ec2-user@${PUBLIC_IP} 'tail -f /var/log/aurea-init.log'"
