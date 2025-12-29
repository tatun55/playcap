# Shayde Playwright with Japanese Fonts
FROM mcr.microsoft.com/playwright:v1.48.0-noble

# Install font tools and Japanese fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    fontconfig \
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Create font directories
RUN mkdir -p /usr/share/fonts/noto-sans-jp /usr/share/fonts/windows-style /usr/share/fonts/custom

# Download Noto Sans JP (Google Fonts) - All weights 100-900
# Similar to Hiragino Sans (Mac-style) with complete weight coverage
RUN curl -fsSL -o /tmp/noto-sans-jp.zip \
    "https://fonts.google.com/download?family=Noto%20Sans%20JP" && \
    unzip -o /tmp/noto-sans-jp.zip -d /tmp/noto-sans-jp && \
    find /tmp/noto-sans-jp -name "*.ttf" -exec cp {} /usr/share/fonts/noto-sans-jp/ \; && \
    rm -rf /tmp/noto-sans-jp.zip /tmp/noto-sans-jp

# Download BIZ UDGothic - Windows-style Japanese font (free from Google Fonts)
RUN curl -fsSL -o /tmp/bizudgothic.zip \
    "https://github.com/googlefonts/morisawa-biz-ud-gothic/releases/download/v1.05/BIZUDGothic.zip" && \
    unzip -j /tmp/bizudgothic.zip "*.ttf" -d /usr/share/fonts/windows-style/ || true && \
    rm -f /tmp/bizudgothic.zip

# Update font cache
RUN fc-cache -fv

# Verify fonts are installed (Noto Sans JP should show weights like Thin, Light, Regular, Bold, Black)
RUN fc-list | grep -E "(Noto Sans JP|BIZ)" || echo "Some fonts may not be installed"

EXPOSE 3000

CMD ["npx", "playwright", "run-server", "--port", "3000", "--host", "0.0.0.0"]
