#! /bin/bash

PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
#APPDIR=/home/ludo/Desktop/dev
APPDIR=/var/virtual
SOCKET_DIR=/tmp
PID_DIR=/tmp


start() {
    echo "Starting ngfrontman";
    gunicorn_django --daemon --pid=$PID_DIR/ngfrontman.pid --name=ngfrontman --bind=127.0.0.1:9000 --log-file=/tmp/ngfrontman.log settings.py;
    echo "Starting ngfrontman multi";
    gunicorn_django --daemon --pid=$PID_DIR/ngfrontman-multi.pid --name=ngfrontman-multi --bind=127.0.0.1:9001 --log-file=/tmp/ngfrontman.log settings-multi.py;
}

stop() {
    echo "Stopping ngfrontman";
    kill -9 `cat $PID_DIR/ngfrontman.pid`;
    rm -f $PID_DIR/ngfrontman.pid;
    echo "Stopping ngfrontman multi";
    kill -9 `cat $PID_DIR/ngfrontman-multi.pid`;
    rm -f $PID_DIR/ngfrontman-multi.pid;
    rm -f /tmp/ngfrontman.log;
}

reload() {
    echo "Reloading ngfrontman";
    kill -HUP `cat $PID_DIR/ngfrontman.pid`;
    echo "Reloading ngfrontman multi";
    kill -HUP `cat $PID_DIR/ngfrontman-multi.pid`;
}

case "$1" in
  start)
        start
	;;
  stop)
        stop
	;;
  restart)
        reload
    ;;
esac

exit 0
