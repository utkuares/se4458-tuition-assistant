GW=${GATEWAY_URL:-http://localhost:8080}

show() { 
  local label=$1; shift
  local out code
  out=$(curl -s -w '\n%{http_code}' "$@")
  code=$(echo "$out" | tail -n1)
  echo "[$code] $label"
  echo "      $(echo "$out" | sed '$d' | head -c 200)"
}

echo "Gateway: $GW"
echo
echo "== 1. Public route"
show "GET /api/v1/health" "$GW/api/v1/health"

echo
echo "== 2. Protected route without token (blocked by gateway)"
show "GET /api/v1/banking/tuition/20230001, no token" "$GW/api/v1/banking/tuition/20230001"

echo
echo "== 3. Protected route with a fake token (blocked by gateway)"
show "GET /api/v1/banking/tuition/20230001, fake token" \
  -H "Authorization: Bearer abc.def.ghi" "$GW/api/v1/banking/tuition/20230001"

echo
echo "== 4. Login through the gateway, then call the protected route"
TOKEN=$(curl -s -X POST "$GW/api/v1/auth/login" -H "Content-Type: application/json" \
  -d '{"username":"student1","password":"Passw0rd!"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
echo "      token received: ${TOKEN:0:20}..."
show "GET /api/v1/banking/tuition/20230001, valid token" \
  -H "Authorization: Bearer $TOKEN" "$GW/api/v1/banking/tuition/20230001"
show "GET /api/v1/banking/tuition/20230002, valid token of another student" \
  -H "Authorization: Bearer $TOKEN" "$GW/api/v1/banking/tuition/20230002"
show "GET /api/v1/admin/tuition/unpaid, student token" \
  -H "Authorization: Bearer $TOKEN" "$GW/api/v1/admin/tuition/unpaid?term=2026-FALL"

echo
echo "== 5. Mobile route: 3 queries per student per day"
for i in 1 2 3 4; do
  show "GET /api/v1/mobile/tuition/20230003 (query $i)" "$GW/api/v1/mobile/tuition/20230003"
done
echo "      gateway rate-limit headers:"
curl -s -D - -o /dev/null "$GW/api/v1/mobile/tuition/20230002" | grep -i '^x-ratelimit' | sed 's/^/      /'

echo
echo "== 6. Unknown route"
show "GET /api/v2/tuition" "$GW/api/v2/tuition"