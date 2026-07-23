# Camel AI — container image (the enterprise / scaling install path).
#   docker build -t camel-ai .
#   docker run -p 8765:8765 camel-ai                 # dashboard at :8765
#   docker run -e CAMEL_API_KEY=... camel-ai audit https://mysite.com
#
# Reproducible, versioned, no build-from-git on the user's machine. Web + vision
# + dashboard + scheduler + MCP all work headless here (native desktop UIA is
# Windows-only and not available in a Linux container).
FROM python:3.12-slim

ENV CAMEL_HEADLESS=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .

# Install Camel AI + the browser engine and its OS deps in one layer.
RUN pip install ".[vision]" \
 && playwright install --with-deps chromium

EXPOSE 8765
ENTRYPOINT ["camel"]
CMD ["dashboard", "--host", "0.0.0.0", "--no-open"]
