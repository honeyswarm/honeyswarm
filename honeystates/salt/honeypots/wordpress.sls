# This state file deploys a wordpress docker container.
wordpress_app:
  docker_container.running:
    - name: wordpress_app
    - image: wordpress:latest
    - port_bindings: 80:80
    - environment:
      - WORDPRESS_DB_HOST: db:3306
      - WORDPRESS_DB_PASSWORD: wordpress
    - links: wordpress_db:mysql

wordpress_db:
  docker_container.running:
    - name: wordpress_db
    - image: mariadb:latest
    - ports: 3306/tcp
    - environment:
      - MYSQL_ROOT_PASSWORD: wordpress
      - MYSQL_DATABASE: wordpress
      - MYSQL_USER: wordpress
      - MYSQL_PASSWORD: wordpress