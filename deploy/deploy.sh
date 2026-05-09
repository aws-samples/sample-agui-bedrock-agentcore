#!/bin/bash
###############################################################################
# AG-UI Sample — Deploy to AgentCore + CloudFront/S3
#
# 1. Creates CFT stack (IAM roles + S3 bucket + CloudFront)
# 2. Deploys Strands agent to AgentCore Runtime
# 3. Uploads frontend to S3
# 4. Invalidates CloudFront cache
#
# Prerequisites:
#   - AWS CLI configured
#   - Python 3 with boto3 and strands-agents
#
# Usage:
#   ./deploy/deploy.sh
###############################################################################

set -euo pipefail

REGION="${REGION:-us-east-1}"
STACK_NAME="agui-bedrock-agentcore"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "============================================="
echo "AG-UI Sample — AgentCore + CloudFront"
echo "Region: ${REGION}"
echo "============================================="

# ─── Step 1: Create CloudFormation Stack ────────────────────────────────────
echo ""
echo ">>> Step 1: Creating CloudFormation stack..."

STACK_STATUS=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [[ "${STACK_STATUS}" == "DOES_NOT_EXIST" ]]; then
  aws cloudformation create-stack \
    --stack-name ${STACK_NAME} \
    --template-body file://${PROJECT_DIR}/deploy/cloudformation.yaml \
    --capabilities CAPABILITY_NAMED_IAM \
    --region ${REGION}

  echo "  Waiting for stack creation (CloudFront takes ~5 min)..."
  aws cloudformation wait stack-create-complete --stack-name ${STACK_NAME} --region ${REGION}
  echo "  [OK] Stack created"
else
  echo "  Stack already exists (${STACK_STATUS})."
  if [[ "${STACK_STATUS}" == *"COMPLETE"* ]]; then
    echo "  Attempting update..."
    aws cloudformation update-stack \
      --stack-name ${STACK_NAME} \
      --template-body file://${PROJECT_DIR}/deploy/cloudformation.yaml \
      --capabilities CAPABILITY_NAMED_IAM \
      --region ${REGION} 2>/dev/null && \
    aws cloudformation wait stack-update-complete --stack-name ${STACK_NAME} --region ${REGION} || \
    echo "  No updates needed."
  fi
fi

# Get outputs
ROLE_ARN=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} \
  --query 'Stacks[0].Outputs[?OutputKey==`AgentCoreRuntimeRoleArn`].OutputValue' --output text)
FRONTEND_URL=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} \
  --query 'Stacks[0].Outputs[?OutputKey==`FrontendUrl`].OutputValue' --output text)
BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} \
  --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' --output text)
CF_DIST_ID=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' --output text)

echo ""
echo "  AgentCore Role: ${ROLE_ARN}"
echo "  Frontend URL:   ${FRONTEND_URL}"
echo "  S3 Bucket:      ${BUCKET_NAME}"
echo "  CloudFront ID:  ${CF_DIST_ID}"

# ─── Step 2: Deploy AgentCore Agent ─────────────────────────────────────────
echo ""
echo ">>> Step 2: Deploying agent to AgentCore Runtime..."
export AWS_DEFAULT_REGION=${REGION}
python3 ${PROJECT_DIR}/deploy/setup_agentcore.py --create

# ─── Step 3: Upload Frontend and Notebook to S3 ───────────────────────────
echo ""
echo ">>> Step 3: Uploading frontend and notebook to S3..."
aws s3 cp ${PROJECT_DIR}/frontend/index.html s3://${BUCKET_NAME}/index.html \
  --content-type "text/html" --region ${REGION}
aws s3 cp ${PROJECT_DIR}/agui_bedrock_agentcore_deploy.ipynb s3://${BUCKET_NAME}/agui_bedrock_agentcore_deploy.ipynb \
  --content-type "application/x-ipynb+json" --region ${REGION}
echo "  [OK] Frontend and notebook uploaded"

# ─── Step 4: Invalidate CloudFront Cache ────────────────────────────────────
echo ""
echo ">>> Step 4: Invalidating CloudFront cache..."
aws cloudfront create-invalidation \
  --distribution-id ${CF_DIST_ID} \
  --paths "/*" --output text --query 'Invalidation.Id'
echo "  [OK] Cache invalidation submitted"

# ─── Done ───────────────────────────────────────────────────────────────────
echo ""
echo "============================================="
echo "DEPLOYMENT COMPLETE"
echo "============================================="
echo ""
echo "  Frontend (HTTPS): ${FRONTEND_URL}"
echo ""
echo "  Check agent status:"
echo "  python3 deploy/setup_agentcore.py --status"
echo ""
echo "  After frontend changes, re-upload + invalidate:"
echo "  aws s3 cp frontend/index.html s3://${BUCKET_NAME}/index.html --content-type text/html"
echo "  aws cloudfront create-invalidation --distribution-id ${CF_DIST_ID} --paths '/*'"
echo ""
echo "  Cleanup:"
echo "  python3 deploy/setup_agentcore.py --delete"
echo "  aws s3 rm s3://${BUCKET_NAME}/ --recursive"
echo "  aws cloudformation delete-stack --stack-name ${STACK_NAME} --region ${REGION}"
echo "============================================="
