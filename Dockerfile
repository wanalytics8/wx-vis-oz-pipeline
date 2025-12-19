# 1. Use Ubuntu 22.04 base with OpenJDK 17
FROM eclipse-temurin:17-jdk-jammy

# 2. Install Python 3.12 and required tools
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

# 3. Install pip for Python 3.12
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12

# 4. FORCE SYSTEM ALIGNMENT (Added logic here)
# This ensures any background scripts calling 'python3' or 'python' use 3.12
RUN ln -sf /usr/bin/python3.12 /usr/bin/python3
RUN ln -sf /usr/bin/python3.12 /usr/bin/python
RUN python3.12 -m pip install --upgrade pip

# 5. Set the Java Home environment variable for tabula-py
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# 6. Set up the working directory
WORKDIR /app

# 7. Copy and install Python dependencies
# We use the explicit python3.12 binary to bypass any legacy system paths
COPY requirements.txt .
RUN python3.12 -m pip install --no-cache-dir --upgrade -r requirements.txt --ignore-installed blinker

# 8. Copy your main script
COPY main_script_cf.py main.py

# 9. Define the container entry point
# Invoking functions-framework as a module through python3.12 prevents 
# the interpreter from reverting to a legacy version (like 3.8)
CMD ["python3.12", "-m", "functions-framework", "--target=extract_and_load_visualoz", "--port=8080"]
