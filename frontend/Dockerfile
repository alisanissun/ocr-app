FROM docker.io/nginx:alpine

# 複製前端靜態檔案
COPY index.html /usr/share/nginx/html/index.html

# 複製 nginx 設定
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80