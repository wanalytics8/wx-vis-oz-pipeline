# 1. Use a standard Java base image
FROM eclipse-temurin:17-jdk-jammy

# 2. Install the standard Python 3 provided by the OS
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# 3. Set the working directory
WORKDIR /app

# 4. Copy files
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 5. Copy your script
COPY main_script_cf.py main.py

# 6. Revert to the standard execution command
# This uses the default system python3
CMD ["functions-framework", "--target=extract_and_load_visualoz", "--port=8080"]
