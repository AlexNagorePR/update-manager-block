FROM ros:humble

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install Python dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    ros-humble-rmw-cyclonedds-cpp \
     && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Copy and install Python requirements
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY update_manager /app/update_manager

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV CYCLONEDDS_URI=/root/cyclonedds.config.xml

RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc

CMD ["/entrypoint.sh"]