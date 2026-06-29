# Plan: Redirect beta.genomics-resources.uk → genie.genomics-resources.uk

## Background

`beta.genomics-resources.uk` is a legacy EC2 instance (`i-07647078253ae1351`,
`t3.large`) in AWS account `471112938470`, predating the current
`genie.genomics-resources.uk` infrastructure. It runs the same Django/Gunicorn
application via Docker, served through Nginx with a valid Let's Encrypt
certificate.

The goal is to replace the application with a brief informational page that
automatically redirects users to `https://genie.genomics-resources.uk` after a
short delay, so they are informed rather than silently bounced.

---

## Approach

All changes are made directly on the beta server — no Terraform is involved.
The Django/Docker application can remain running untouched. Only the Nginx
configuration changes.

**Mechanism:** Nginx stops proxying to the app and instead serves a single
static HTML page. The page:
- Explains that the beta site has moved
- Provides a direct link in case the redirect does not fire
- Redirects to `https://genie.genomics-resources.uk` after 8 seconds via
  `<meta http-equiv="refresh">`

This is the simplest approach with no application code changes and a clean
rollback path.

---

## Implementation Steps

### Step 1 — Write the redirect page

Create `/var/www/html/moved.html` on the beta server:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="refresh" content="8; url=https://genie.genomics-resources.uk">
  <title>GENIE has moved</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #f0f4f8;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
    }
    .box {
      background: white;
      border-top: 6px solid #005eb8;
      border-radius: 4px;
      padding: 2.5rem 3rem;
      max-width: 540px;
      text-align: center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    h1 { color: #005eb8; font-size: 1.5rem; margin-bottom: 1rem; }
    p  { color: #333; line-height: 1.6; }
    a  { color: #005eb8; font-weight: bold; }
    .countdown { font-size: 2rem; font-weight: bold; color: #005eb8; margin: 1.5rem 0; }
  </style>
  <script>
    var seconds = 8;
    function tick() {
      var el = document.getElementById('count');
      if (el) { el.textContent = seconds; }
      if (seconds <= 0) {
        window.location.href = 'https://genie.genomics-resources.uk';
      }
      seconds--;
      setTimeout(tick, 1000);
    }
    window.onload = tick;
  </script>
</head>
<body>
  <div class="box">
    <h1>GENIE has a new home</h1>
    <p>
      The NHS GENIE database has been updated to release 19 and has moved to a new address (please update your bookmarks).
      You will be redirected automatically in:
    </p>
    <div class="countdown"><span id="count">8</span>s</div>
    <p>
      If you are not redirected, please click the link below:
    </p>
    <p>
      <a href="https://genie.genomics-resources.uk">
        https://genie.genomics-resources.uk
      </a>
    </p>
  </div>
</body>
</html>
```

### Step 2 — Update the Nginx configuration

Replace the `proxy_pass` block in the `beta.genomics-resources.uk` server
block with a directive to serve `moved.html` for all requests:

**Current `location /` block** (same proxy pattern as `scripts/nginx-genie.conf`):
```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**Replace with:**
```nginx
location / {
    root /var/www/html;
    try_files /moved.html =404;
}
```

### Step 3 — Test and reload Nginx

```bash
sudo nginx -t && sudo systemctl reload nginx
```

### Step 4 — Verify

- Visit `https://beta.genomics-resources.uk` — the informational page should
  appear and redirect to `https://genie.genomics-resources.uk` after 8 seconds.
- Confirm `https` works (existing Let's Encrypt cert is still valid and managed
  by Certbot).
- Confirm `http://beta.genomics-resources.uk` still redirects to `https`
  (existing Certbot-managed HTTP→HTTPS redirect remains untouched).

---

## Rollback

To restore the original behaviour, revert the `location /` block to its
previous state (see Step 2 above for the full original block) and reload Nginx:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

The Docker application remains running throughout and can be proxied again
immediately without any restart.

---

## Future: Decommissioning the Server

Once satisfied that users have transitioned, the beta server can be stopped and
eventually terminated. Before doing so:

1. Confirm the Let's Encrypt cert renewal cron is not depended on elsewhere.
2. Check whether `genomics-resources.uk` Route 53 hosted zone and any other
   DNS records in account `471112938470` need to be preserved.
3. Terminate `i-07647078253ae1351` and release the associated EIP/public IP.
4. Consider whether the `genomics-resources.uk` domain registration and hosted
   zone should be migrated to the `804761969039` account or allowed to lapse.
