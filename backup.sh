#!/bin/bash
BACKUP_DIR="/opt/getcourse/backups"
DATE=$(date +%F_%H-%M-%S)
mkdir -p $BACKUP_DIR
docker exec pgdb pg_dump -U max get_course_td_bot -F c -f /tmp/db_backup_$DATE.dump
docker cp pgdb:/tmp/db_backup_$DATE.dump $BACKUP_DIR/db_backup_$DATE.dump
docker exec pgdb rm /tmp/db_backup_$DATE.dump
find $BACKUP_DIR -type f -mtime +7 -delete