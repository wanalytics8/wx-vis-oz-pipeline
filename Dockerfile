# Use Ubuntu 22.04 base with OpenJDK 17
FROM eclipse-temurin:17-jdk-jammy

# Install Python 3.12 and required tools
RUN apt-get update && apt-get install -y \
    software-properties-common \
    curl \
    && add-apt-repository ppa:deadsnakes/ppa -y \
    && apt-get update \
    && apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    && rm -rf /var/lib/apt/lists/*

# Install pip for Python 3.12
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12

# Set python3 to point to python3.12
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1


# 3. Set the Java Home environment variable for tabula-py
ENV JAVA_HOME /usr/lib/jvm/java-17-openjdk-amd64

# 4. Set up the working directory inside the container
WORKDIR /app

# 5. Copy and install Python dependencies
COPY requirements.txt .
RUN python3.12 -m pip install --no-cache-dir --upgrade -r requirements.txt --ignore-installed blinker

# 6. Copy your main script (rename is optional, but common practice)
COPY main_script_cf.py main.py

# 7. Define the container entry point (runs your script as a service)
# don't invoke functions-framework directly which hash-bang invokes own py3.8
CMD ["python3.12", "-m", "functions-framework", "--target=extract_and_load_visualoz", "--port=8080"]
