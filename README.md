# Nginx Features Lab (notes-proxy-lab)

A small Notes app: Nginx in front, a Flask api, and PostgreSQL. Only Nginx is open to the outside. I used this project to practice the main Nginx features.

```
Browser → Nginx (8080 http, 8443 https) → api (3 copies, port 5000) → db (5432)
```

## Folder structure
```
notes-proxy-lab/
├── docker-compose.yml
├── nginx.conf
├── .gitignore          (contains: certs/)
├── html/
│   └── index.html
├── certs/              (self-signed certificate, not pushed to GitHub)
└── api/
    ├── app.py
    ├── requirements.txt
    └── Dockerfile
```

## Features and how each one is done

| Feature | How it is done |
|---|---|
| Reverse proxy | `proxy_pass` forwards the request to a hidden backend |
| One address for many apps | `/` gives the page, `/api/` goes to the api |
| Path routing | `location` blocks, the most specific match wins |
| Hiding backends | Only `nginx` has `ports:` in docker-compose.yml |
| Path rewriting | The `/` at the end of `proxy_pass` removes `/api` from the path |
| Serving files directly | `root` and `index` serve `index.html` from a mounted folder |
| Logging | Default access log, see it with `docker compose logs nginx` |
| Rate limiting | `limit_req_zone` and `limit_req`, blocked requests get 429 |
| Compression | `gzip on` for text, CSS, JS, JSON |
| Redirect | `return 301` for a moved path and for HTTP to HTTPS |
| Access control | `deny all;` on `/admin/` gives 403 |
| Load balancing | `upstream` group plus `--scale api=3`, round robin |
| HTTPS | `listen 443 ssl` with a certificate and key |

## Final nginx.conf
```nginx
events {}

http {
  include /etc/nginx/mime.types;

  gzip on;
  gzip_min_length 256;
  gzip_types text/plain text/css application/javascript application/json;

  limit_req_zone $binary_remote_addr zone=api_limit:10m rate=5r/s;

  upstream api_servers {
    server api:5000;
  }

  server {
    listen 80;

    location / {
      return 301 https://$host:8443$request_uri;
    }
  }

  server {
    listen 443 ssl;

    ssl_certificate /etc/nginx/certs/selfsigned.crt;
    ssl_certificate_key /etc/nginx/certs/selfsigned.key;

    location / {
      root /usr/share/nginx/html;
      index index.html;
    }

    location = /old-notes {
      return 301 $scheme://$http_host/;
    }

    location /admin/ {
      deny all;
    }

    location /api/ {
      limit_req zone=api_limit burst=5 nodelay;
      limit_req_status 429;
      add_header X-Upstream $upstream_addr always;
      proxy_pass http://api_servers/;
    }
  }
}
```

## Final docker-compose.yml
```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: notesdb
      POSTGRES_USER: notesuser
      POSTGRES_PASSWORD: notespass
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U notesuser -d notesdb"]
      interval: 5s
      timeout: 3s
      retries: 10

  api:
    build: ./api
    environment:
      DB_HOST: db
      DB_NAME: notesdb
      DB_USER: notesuser
      DB_PASSWORD: notespass
    depends_on:
      db:
        condition: service_healthy

  nginx:
    image: nginx:latest
    ports:
      - "8080:80"
      - "8443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./html:/usr/share/nginx/html:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - api

volumes:
  db_data:
```

## Create the self-signed certificate
```bash
mkdir certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/selfsigned.key \
  -out certs/selfsigned.crt \
  -subj "/CN=localhost"
```

## Run and test
```bash
# start, with 3 copies of the api
docker compose up -d --build --scale api=3

# page in the browser (accept the certificate warning)
https://localhost:8443/

# api over HTTPS (-k accepts the self-signed certificate)
curl -k -i https://localhost:8443/api/notes

# HTTP is redirected to HTTPS
curl -i http://localhost:8080/api/notes

# which api copy answered (load balancing)
for i in $(seq 1 6); do curl -k -s -D - -o /dev/null https://localhost:8443/api/notes | grep X-Upstream; sleep 0.3; done

# rate limiting: first few 200, then 429
for i in $(seq 1 20); do curl -k -s -o /dev/null -w "%{http_code}\n" https://localhost:8443/api/notes; done

# compression: second number is smaller
curl -k -s -o /dev/null -w "%{size_download}\n" https://localhost:8443/
curl -k -s -H "Accept-Encoding: gzip" -o /dev/null -w "%{size_download}\n" https://localhost:8443/

# redirect and access control
curl -k -i https://localhost:8443/old-notes     # 301
curl -k -i https://localhost:8443/admin/        # 403

# api is hidden, this fails
curl http://localhost:5000/notes

# logs
docker compose logs -f nginx

# stop (notes are kept)
docker compose down

# stop and delete the db volume (notes are gone)
docker compose down -v
```

## Things I learned
- Nginx is a web server (serves files) and a reverse proxy (forwards requests to apps)
- `docker compose down` keeps the volume, `down -v` deletes it
- Nginx finds the api copies when it starts, so recreate Nginx after scaling: `docker compose up -d --force-recreate nginx`
- In the log, the client IP is the Docker gateway (like 172.19.0.1), not my real IP
- Browsers remember a 301 redirect, so test with Disable cache or a private window
- Real certificates come from a trusted authority (like Let's Encrypt). A self-signed one only gives a browser warning.
- Never push private keys to GitHub, so `certs/` is in `.gitignore`
- An Ingress in Kubernetes does the same jobs: routing, HTTPS, rate limiting, rewriting
