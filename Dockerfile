FROM ros:humble-ros-base

WORKDIR /app

RUN apt-get update && apt-get install -y \
    python3-pip \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY main.py /app/main.py

CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && python3 /app/main.py"]