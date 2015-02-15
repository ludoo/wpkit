#! /bin/bash

PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
APPDIR=/home/ludo/Desktop/dev
SOCKET_DIR=/tmp
PID_DIR=/tmp


start() {
    for i in '' '-multi' ; do
        echo "Starting ngfrontman$i using ngfrontman.settings$i.py";
        DJANGO_SETTINGS_MODULE=ngfrontman.settings${i} $APPDIR/wp/ngfrontman/manage.py runfcgi method=prefork socket=$SOCKET_DIR/ngfrontman$i.sock pidfile=$PID_DIR/ngfrontman$i.pid maxchildren=2 maxspare=1;
        chmod a+rw $SOCKET_DIR/ngfrontman$i.sock;
        chmod 660 $SOCKET_DIR/ngfrontman$i.pid;
    done
}

stop() {
    for i in '' '-multi' ; do
        echo "Stopping ngfrontman$i";
        kill -9 `cat $PID_DIR/ngfrontman$i.pid`;
        rm -f $SOCKET_DIR/ngfrontman$i.sock;
        rm -f $PID_DIR/ngfrontman$i.pid;
    done
}

case "$1" in
  start)
        start
	;;
  stop)
        stop
	;;
  restart)
    stop
    sleep 1
    start
    ;;
esac

exit 0
