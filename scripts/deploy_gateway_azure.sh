#!/bin/bash
# Build the Kong + API image and deploy it as one Container App.
# Run from the repo root: ./scripts/deploy_gateway_azure.sh
set -e

set -a
source azure.env
set +a
TAG=v6
IMAGE=$ACR.azurecr.io/tuition-gateway:$TAG

echo "1/4 Cleaning up"
az containerapp env delete -n tuition-env2 -g "$RG" -y --no-wait -o none 2>/dev/null || true
az containerapp delete -n tuition-gateway -g "$RG" -y -o none 2>/dev/null || true
sed -i '' '/GW_FQDN/d;/ENV_NAME=tuition-env2/d' azure.env

echo "2/4 Building image $IMAGE"
.venv/bin/python scripts/render_kong_config.py --upstream http://localhost:8000 --output gateway/kong.azure.yml
docker buildx build --platform linux/amd64 -t "$IMAGE" -f gateway/Dockerfile --push .

echo "3/4 Creating app tuition-gateway"
ACR_USER=$(az acr credential show -n "$ACR" --query username -o tsv)
ACR_PASS=$(az acr credential show -n "$ACR" --query "passwords[0].value" -o tsv)
az containerapp create -n tuition-gateway -g "$RG" --environment tuition-env \
  --image "$IMAGE" \
  --registry-server "$ACR.azurecr.io" --registry-username "$ACR_USER" --registry-password "$ACR_PASS" \
  --ingress external --target-port 8080 \
  --cpu 0.5 --memory 1Gi --min-replicas 1 --max-replicas 1 \
  --secrets "db-url=$AZ_DATABASE_URL" \
            "jwt-private=$(base64 -i keys/jwt_private.pem)" \
            "jwt-public=$(base64 -i keys/jwt_public.pem)" \
  --env-vars DATABASE_URL=secretref:db-url \
             JWT_PRIVATE_KEY_B64=secretref:jwt-private \
             JWT_PUBLIC_KEY_B64=secretref:jwt-public \
  -o none

GW_FQDN=$(az containerapp show -n tuition-gateway -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)
echo "export GW_FQDN=$GW_FQDN" >> azure.env
echo "    gateway: https://$GW_FQDN"
echo "    waiting 60s for Kong and the API to start"
sleep 60

echo "4/4 Smoke test"
GATEWAY_URL="https://$GW_FQDN" ./gateway/smoke_test.sh | tee docs/logs/gateway_demo_azure.txt
