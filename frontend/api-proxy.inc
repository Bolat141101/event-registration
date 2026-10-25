set $api_upstream api:8000;
proxy_pass http://$api_upstream;
proxy_http_version 1.1;
proxy_set_header Host $host;
proxy_set_header Connection "";
# Overwrite, never append untrusted client-supplied proxy headers.
proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header X-Real-IP $remote_addr;
proxy_buffering off;
proxy_cache off;
proxy_read_timeout 60s;
