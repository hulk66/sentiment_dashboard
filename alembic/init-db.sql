CREATE DATABASE IF NOT EXISTS sentiment;
CREATE USER 'sentiment'@'%' IDENTIFIED BY 'sentiment';
GRANT ALL PRIVILEGES ON sentiment.* TO 'sentiment'@'%';