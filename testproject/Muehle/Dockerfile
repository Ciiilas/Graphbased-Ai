# Stage 1: Build image
FROM sbtscala/scala-sbt:eclipse-temurin-jammy-22_36_1.10.0_3.4.2

# Setze den Arbeitsverzeichnis
WORKDIR /app

# Install curl and gnupg2 to handle SBT download
RUN apt-get update && apt-get install -y curl gnupg2 x11-apps
RUN apt-get update && apt-get install -y \
    libxext6 \
    libxrender1 \
    libxtst6 \
    libxi6 \
    libxrandr2 \
    libgtk-3-0

# Download sbt and install
RUN curl -sL https://dlcdn.apache.org/sbt/debian/sbt-1.9.4.deb -o sbt.deb

# Install sbt using dpkg and resolve missing dependencies
RUN dpkg -i sbt.deb || apt-get install -f -y

# Download and cache sbt dependencies
RUN sbt update

# Erstelle die Dateien SaveGame.json und SaveGame.xml, falls sie nicht existieren
RUN touch SaveGame.json SaveGame.xml

# Copy the rest of the application code
COPY . /app

# Setze die Umgebungsvariablen für SBT
ENV SBT_OPTS="-Xms512M -Xmx1536M -Xss2M -XX:MaxMetaspaceSize=512M"

# Baue das Projekt
RUN sbt compile

# Führe das Projekt aus
CMD ["sbt", "run"]

# docker run -it --rm \
  #  -e DISPLAY=host.docker.internal:0 \
  #  -v /tmp/.X11-unix:/tmp/.X11-unix \
  #  muehle