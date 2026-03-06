# Render Deployment

## Recommendation

Use one Render Docker web service for the full app and serve the portals from the backend:

- `/frontend/student/index.html`
- `/frontend/admin/index.html`
- `/frontend/guard/index.html`
- `/frontend/parent/index.html`

This project is a better fit for a long-running Docker service than a serverless setup because it uses:

- `face-recognition` and `dlib`
- OpenCV and image uploads
- geofencing checks
- long-lived authenticated API flows

## Which Database To Use

### Best choice: keep your existing Render Postgres

Use your current Render PostgreSQL database if all of these are true:

- it already contains the project data you need
- it is not an expiring test database you plan to throw away
- it is reachable from the Render web service

### Use Supabase only if needed

Use Supabase Postgres only if:

- your Render Postgres no longer exists
- your Render Postgres is a disposable free trial you do not want to rely on
- you want a separate managed Postgres outside Render

## Step 1: Prepare The Repo

1. Push the current repo to GitHub.
2. Keep [Dockerfile](/home/madhu/smart Gate/Dockerfile) in the repo root.
3. Keep [render.yaml](/home/madhu/smart Gate/render.yaml) in the repo root.
4. Keep [backend/.env example reference](/home/madhu/smart Gate/.env.example) only as a template. Do not commit real secrets.

## Step 2A: Use Existing Render Postgres

1. Open Render dashboard.
2. Open your PostgreSQL service.
3. Copy the connection string.
4. Prefer the Internal Database URL if the web service is in the same Render region.
5. Keep that value ready for `DATABASE_URL`.

## Step 2B: Supabase Setup, Exact Steps

Do this only if you need a new database.

1. Open `https://supabase.com/dashboard`.
2. Sign in.
3. Create an organization if Supabase asks for one.
4. Click `New project`.
5. Choose the organization.
6. Enter a project name.
7. Set a strong database password and save it somewhere safe.
8. Choose the region closest to your Render web service.
9. Click `Create new project`.
10. Wait until the project finishes provisioning.
11. Open the project.
12. Go to `Project Settings`.
13. Open `Database`.
14. Find the connection string section.
15. Choose the direct PostgreSQL connection string, not the pooled HTTP API URL.
16. Copy the URI.
17. Replace the placeholder password in the URI if Supabase shows it separately.
18. Keep that value ready for `DATABASE_URL` in Render.

## Step 3: Create The Render Web Service

1. Open Render dashboard.
2. Click `New +`.
3. Click `Web Service`.
4. Connect your GitHub repo.
5. Select this repository.
6. Choose the branch you want to deploy.
7. For runtime, choose `Docker`.
8. Render should detect [Dockerfile](/home/madhu/smart Gate/Dockerfile).
9. Pick a service name, for example `smart-gate-system`.
10. Choose a region close to the database.
11. Choose the plan.

## Step 4: Add Render Environment Variables

Set these in the Render web service before the first deploy:

```env
DATABASE_URL=postgresql://...
SECRET_KEY=use_a_long_random_secret_here
JWT_SECRET=use_a_different_long_random_secret_here
ACCESS_TOKEN_EXPIRE_MINUTES=720
QR_TTL_MINUTES=15
SELF_REGISTRATION_ENABLED=false
ACCOUNT_REQUESTS_ENABLED=true
SMARTGATE_SEED_MODE=never
FACE_AUTH_ENABLED=true
FACE_AUTH_BACKEND=opencv
NOTIFICATIONS_ENABLED=false
GEOFENCE_ENABLED=true
```

Optional notification variables:

```env
FIREBASE_CREDENTIALS_JSON={"type":"service_account",...}
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=...
```

Notes:

- `SMARTGATE_SEED_MODE=never` avoids reseeding demo users into production data.
- `ACCOUNT_REQUESTS_ENABLED=true` keeps the approval workflow active.
- `SELF_REGISTRATION_ENABLED=false` prevents direct account creation.
- `FACE_AUTH_ENABLED=true` enables biometric registration and verification.
- `FACE_AUTH_BACKEND=opencv` uses the lightweight backend intended for Render deployments.
- `NOTIFICATIONS_ENABLED=false` is the safe default unless you also configure Firebase or Twilio.
- Admins still get in-app request alerts in the dashboard UI even if push notifications stay off.

## Step 5: Deploy

1. Click `Create Web Service` or `Deploy latest commit`.
2. Wait for the Docker build to finish.
3. Open the service once the deploy succeeds.
4. Check `https://your-service.onrender.com/healthz`.
5. Open `https://your-service.onrender.com/`. It should redirect to the frontend landing page.
6. If that works, also test the direct portal URLs:
   - `https://your-service.onrender.com/frontend/admin/`
   - `https://your-service.onrender.com/frontend/student/`
   - `https://your-service.onrender.com/frontend/guard/`
   - `https://your-service.onrender.com/frontend/parent/`

## Step 6: First Production Validation

Test these in order:

1. Admin login works.
2. Student or personnel account request submission works.
3. Admin can approve the request.
4. Approved user can log in.
5. Pass creation and approval work.
6. Guard scan works.
7. Geofence location check works.
8. Face verification works if enabled.

## Face Recognition Reality On Render

This feature is the heaviest part of the stack.

- It is technically deployable on Render Docker.
- It is not a good fit for a lightweight or short-lived runtime.
- Free instances may build slowly and restart more often.
- If face recognition must be reliable, use at least a paid Render web service.

## Geofence / Location Reality On Render

This part is much easier than face recognition.

- Geofencing should work fine on Render if the Docker build succeeds.
- Browser location permission still depends on the user device and browser.
- The backend geofence logic is already part of this app.

## Should You Use Render Free

For testing: yes, possibly.

For stable real use with face recognition: no, not ideal.

Use Render free only if you want to:

- verify that the app boots
- test login and basic API flows
- test the registration approval workflow

Move to a paid Render web service when you need:

- reliable face recognition
- fewer cold starts
- more predictable memory
- stable day-to-day usage

## What I Recommend

1. Keep the existing Render Postgres if it is already the real project database.
2. Deploy the app as one Render Docker web service.
3. Start with Render free only as a smoke-test if you want.
4. Move the web service to a paid plan for real face-recognition usage.
5. Use Supabase only if you need a new persistent Postgres database.
