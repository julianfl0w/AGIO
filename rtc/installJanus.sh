sudo apt update

sudo apt install -y libmicrohttpd-dev libjansson-dev \
	libssl-dev libsofia-sip-ua-dev libglib2.0-dev \
	libopus-dev libogg-dev libcurl4-openssl-dev liblua5.3-dev \
	libconfig-dev pkg-config libtool automake aptitude \
    python3-pip python3-setuptools python3-wheel ninja-build cmakec

sudo apt install python3-mesonpy 

git clone https://gitlab.freedesktop.org/libnice/libnice
cd libnice
meson --prefix=/usr build && ninja -C build && sudo ninja -C build install
cd .. 
sudo apt install libsrtp2-dev

git clone https://github.com/sctplab/usrsctp
cd usrsctp
./bootstrap
./configure --prefix=/usr --disable-programs --disable-inet --disable-inet6
make && sudo make install
cd .. 
libtool --finish /usr/lib
export PATH=$PATH:/usr/lib

sudo aptitude install doxygen graphviz

git clone https://github.com/meetecho/janus-gateway.git
cd janus-gateway

sh autogen.sh

./configure --prefix=/opt/janus --disable-websockets --disable-rabbitmq --disable-mqtt

make
sudo make install

sudo make configs
# ./configure --disable-websockets --disable-data-channels --disable-rabbitmq --disable-mqtt

#


# Create systemd service file
cat << EOF | sudo tee /etc/systemd/system/janus.service
[Unit]
Description=Janus WebRTC Server
After=network.target

[Service]
Type=simple
ExecStart=/opt/janus/bin/janus
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable janus

# Start the service
sudo systemctl start janus

# Check status
sudo systemctl status janus

sudo chmod 777 /.secrets
cd /.secrets
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# turn https on
sudo vim /opt/janus/etc/janus/janus.transport.http.jcfg