import urllib.request
import json
import base64

wp_url = "https://www.techjobs360.com"
user = "admin"
pwd = "vgPl O24r nMOq dRF7 GhBN i9l4"
auth_str = base64.b64encode(f"{user}:{pwd}".encode("utf-8")).decode("utf-8")
headers = {"Authorization": f"Basic {auth_str}", "Content-Type": "application/json"}

# 1. Update Snippet 193
req = urllib.request.Request(f"{wp_url}/wp-json/code-snippets/v1/snippets/193", headers=headers)
with urllib.request.urlopen(req) as res:
    snippet = json.loads(res.read())

code = snippet["code"]
code = code.replace("add_action('template_redirect', function() {", "add_action('init', function() {")

payload = json.dumps({"code": code, "active": True}).encode("utf-8")
req_update = urllib.request.Request(f"{wp_url}/wp-json/code-snippets/v1/snippets/193", data=payload, headers=headers, method="POST")
with urllib.request.urlopen(req_update) as res_u:
    print("Updated Snippet 193 with early init redirect!")

# 2. Test fetching /terms-of-service/
try:
    req_test = urllib.request.Request(f"{wp_url}/terms-of-service/", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req_test, timeout=10) as res_t:
        print("Live test /terms-of-service/ ->", res_t.geturl(), "Status:", res_t.status)
except Exception as e:
    print("Test notice:", e)
