FROM python:3.13-slim

# Set timezone to Europe/Helsinki
ENV TZ=Europe/Helsinki
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && ln -snf /usr/share/zoneinfo/Europe/Helsinki /etc/localtime \
    && echo "Europe/Helsinki" > /etc/timezone \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy the content of the local src directory to the working directory
COPY . .

# Command to run on container start
CMD ["python", "cleaning_bot.py" ]