# CP-C fixture image: a real ROS 2 Humble with both bridges and a self-signed cert.
# Each test scenario runs this image with a different launch command (rosbridge /
# foxglove, default / nonstandard port, plain / TLS) and asserts detection matches.
FROM ros:humble

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ros-humble-foxglove-bridge \
      ros-humble-rosbridge-suite \
      openssl \
 && rm -rf /var/lib/apt/lists/*

# Self-signed cert for the TLS (secure=1) scenario.
RUN mkdir -p /certs \
 && openssl req -x509 -newkey rsa:2048 -nodes \
      -keyout /certs/key.pem -out /certs/cert.pem -days 3650 \
      -subj "/CN=localhost"
