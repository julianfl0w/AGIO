apt install libmicrohttpd-dev libjansson-dev \
	libssl-dev libsofia-sip-ua-dev libglib2.0-dev \
	libopus-dev libogg-dev libcurl4-openssl-dev liblua5.3-dev \
	libconfig-dev pkg-config libtool automake aptitude

git clone https://gitlab.freedesktop.org/libnice/libnice
cd libnice
meson --prefix=/usr build && ninja -C build && sudo ninja -C build install
cd .. 

git clone https://github.com/sctplab/usrsctp
cd usrsctp
./bootstrap
./configure --prefix=/usr --disable-programs --disable-inet --disable-inet6
make && sudo make install
cd .. 

aptitude install doxygen graphviz

git clone https://github.com/meetecho/janus-gateway.git
cd janus-gateway

sh autogen.sh

./configure --prefix=/opt/janus
make
make install

make configs
# ./configure --disable-websockets --disable-data-channels --disable-rabbitmq --disable-mqtt
./configure --disable-websockets --disable-rabbitmq --disable-mqtt

