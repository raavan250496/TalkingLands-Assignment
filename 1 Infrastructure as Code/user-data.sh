#!/bin/bash
apt update -y
apt install nginx -y
systemctl enable nginx
systemctl start nginx

cat > /var/www/html/index.html <<EOF
<html>
  <head><title>${environment} - Associate DevOps Engineer Assignment</title></head>
  <body>
    <h1>${custom_message}</h1>
    </body>
</html>
EOF
