# 1. Base Image: Start with a slim and secure Python base image.
FROM python:3.12-slim

# 2. Environment Variables:
#    - Prevents Python from writing .pyc files.
#    - Ensures logs are sent straight to the container logs without buffering.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Create a non-root user for security.
#    - Creates a new group 'appgroup' and a new user 'appuser'.
#    - --no-create-home: We don't need a home directory.
#    - --disabled-password: This user cannot log in.
RUN addgroup --system appgroup && adduser --system --group --no-create-home --disabled-password appuser

# 4. Set the working directory.
WORKDIR /app

# 5. Copy and install dependencies.
#    - Copying requirements.txt first leverages Docker's layer caching.
#    - If requirements.txt doesn't change, Docker won't reinstall packages on every build.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy the rest of the application code.
COPY . .

# 7. Change ownership of the app directory to the new non-root user.
RUN chown -R appuser:appgroup /app

# 8. Switch to the non-root user.
USER appuser

# 9. Define the command to run the application.
CMD ["python", "main.py"]