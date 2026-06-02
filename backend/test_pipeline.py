"""
Full end-to-end pipeline test: register -> login -> create project -> generate -> poll status
"""
import json, time, urllib.request, urllib.error, urllib.parse

BASE = "http://127.0.0.1:8000"

def req(method, path, body=None, token=None, is_form=False):
    if is_form:
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = urllib.parse.urlencode(body).encode() if body else None
    else:
        headers = {"Content-Type": "application/json"}
        data = json.dumps(body).encode() if body else None
        
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, str(e)

print("=== 1. Register ===")
s, b = req("POST", "/auth/register", {"email": "test@nex.ai", "password": "Test1234!", "full_name": "Test User"})
print(s, b)
token = None
if s in (200, 201):
    token = b.get("access_token")

print("\n=== 2. Login ===")
if not token:
    s, b = req("POST", "/auth/login", {"username": "test@nex.ai", "password": "Test1234!"}, is_form=True)
    print(s, b)
    if s != 200:
        print("LOGIN FAILED — stopping")
        exit(1)
    token = b["access_token"]
else:
    print("Already registered & logged in via registration response.")


print("\n=== 3. Create Project ===")
s, b = req("POST", "/projects/create", {"name": "Test House", "prompt": "A test architectural project prompt", "style": "modern"}, token)
print(s, b)
if s not in (200, 201):
    print("PROJECT CREATION FAILED — stopping")
    exit(1)
project_id = b["id"]

print("\n=== 4. Trigger Generation ===")
s, b = req("POST", "/generate/floorplan", {
    "project_id": project_id,
    "prompt": "3 bedroom modern house with open kitchen, 2 bathrooms and a living room, 120 sqm",
    "style": "modern"
}, token)
print(s, b)
if s not in (200, 202):
    print("GENERATION FAILED — stopping")
    exit(1)
job_id = b["job_id"]

print(f"\n=== 5. Poll Status (job_id={job_id}) ===")
for i in range(30):
    time.sleep(3)
    s, b = req("GET", f"/generate/status/{job_id}", token=token)
    status = b.get("status", "?")
    stage  = b.get("current_stage", "?")
    pct    = b.get("progress_percent", 0)
    print(f"  [{i*3}s] {status} | {stage} | {pct}%")
    if status in ("COMPLETED", "FAILED"):
        print("\nFinal job result:", json.dumps(b, indent=2))
        break
else:
    print("TIMEOUT — job still running after 90s")
