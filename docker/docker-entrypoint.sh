#!/bin/sh
# ==================== 启动脚本 ====================
# 用 envsubst 渲染 nginx 模板，再启动 nginx。
#   BACKEND_UPSTREAM  反代上游，默认 http://backend:8000（docker-compose 服务名）
# ===================================================
set -e

: "${BACKEND_UPSTREAM:=http://backend:8000}"
export BACKEND_UPSTREAM

# 渲染 /etc/nginx/conf.d/default.conf（模板与目标同名，envsubst 覆盖写回）
envsubst '${BACKEND_UPSTREAM}' < /etc/nginx/conf.d/default.conf \
    > /etc/nginx/conf.d/default.conf.rendered
mv /etc/nginx/conf.d/default.conf.rendered /etc/nginx/conf.d/default.conf

echo "[nginx] BACKEND_UPSTREAM=${BACKEND_UPSTREAM}"
echo "[nginx] starting nginx..."

exec nginx -g 'daemon off;'
